"""Analise de movimento anormal de preco.

Responde "este movimento e anormal para este ativo?" — nao "para onde ele vai".
O z-score compara o retorno acumulado desde o fechamento anterior com a
volatilidade tipica daquele ativo naquela hora da sessao.

Por que sigma empirico por indice horario e nao escala sqrt(tempo):
a barra de abertura carrega o gap noturno inteiro. Medido no JEPQ (1 ano de
barras horarias), sigma na abertura = 0,76% contra 0,95% no fim do dia, ou seja
80% da vol diaria ja esta no gap. A escala sqrt(t) preveria 0,36% na abertura e
inflava o z por ~2,1x: no backtest, 10 de 12 alertas eram falsos 09:30.
"""

import json
import math
import os
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

_YF = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
_UA = {"User-Agent": "Mozilla/5.0"}

# Ajustaveis por env: mudar o limiar nao deve exigir rebuild da imagem
LIMIAR_ALERTA = float(os.getenv("VOL_LIMIAR_ALERTA", "2.0"))    # z minimo para avisar
PIORA_REALERTA = float(os.getenv("VOL_PIORA_REALERTA", "1.0"))  # reavisa se piorar 1 sigma
_MIN_AMOSTRAS = 20        # dias minimos por bucket horario
_TTL_CURVA = 86400        # curva de sigma vale 1 dia
_TTL_DEDUP = 172800       # marca de alerta sobrevive ao fim de semana

_redis = None
_db = None
_log = None


def configurar(redis_client=None, db_getter=None, logger=None):
    """Injeta dependencias do main (evita import circular)."""
    global _redis, _db, _log
    _redis = redis_client
    _db = db_getter
    _log = logger


def _erro(msg):
    if _log:
        _log.error(msg)


# ── Yahoo Finance ────────────────────────────────────────────────────────────

async def _chart(ticker: str, rng: str, itv: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=25.0) as c:
            r = await c.get(_YF.format(t=ticker),
                            params={"range": rng, "interval": itv}, headers=_UA)
        if r.status_code != 200:
            _erro(f"VOL_YF_HTTP ticker={ticker} range={rng} status={r.status_code}")
            return None
        res = (r.json().get("chart") or {}).get("result") or []
        return res[0] if res else None
    except Exception as e:
        _erro(f"VOL_YF_ERROR ticker={ticker} range={rng} error={e}")
        return None


def _closes(d: dict) -> list:
    """[(epoch, fechamento)] descartando barras sem fechamento."""
    ts = d.get("timestamp") or []
    q = ((d.get("indicators") or {}).get("quote") or [{}])[0]
    return [(t, c) for t, c in zip(ts, q.get("close") or []) if c]


def _tz(meta: dict) -> timezone:
    """Fuso da bolsa. Yahoo entrega o offset ja com horario de verao aplicado,
    entao nao ha DST para tratar na mao."""
    return timezone(timedelta(seconds=meta.get("gmtoffset") or 0))


# ── Curva de sigma por hora da sessao ────────────────────────────────────────

async def _calcular_curva(ticker: str) -> Optional[dict]:
    """{indice_horario: sigma} do retorno log acumulado desde o fechamento
    anterior. O dia corrente e excluido para nao contaminar a base."""
    diario = await _chart(ticker, "1y", "1d")
    horario = await _chart(ticker, "1y", "1h")
    if not diario or not horario:
        return None

    tz = _tz(diario.get("meta") or {})
    dias = [(datetime.fromtimestamp(t, tz).date(), c) for t, c in _closes(diario)]
    if len(dias) < 30:
        return None
    anterior = {dias[i][0]: dias[i - 1][1] for i in range(1, len(dias))}
    hoje = datetime.now(tz).date()

    sessoes = {}
    for t, c in _closes(horario):
        d = datetime.fromtimestamp(t, tz).date()
        if d == hoje:
            continue
        sessoes.setdefault(d, []).append((t, c))

    buckets = {}
    for d, barras in sessoes.items():
        if d not in anterior or len(barras) < 5:   # pula feriado / meio pregao
            continue
        pc = anterior[d]
        for i, (_, c) in enumerate(sorted(barras)):
            buckets.setdefault(i, []).append(math.log(c / pc))

    curva = {str(i): statistics.stdev(v)
             for i, v in buckets.items() if len(v) >= _MIN_AMOSTRAS}
    return curva or None


def _curva_db_salvar(ticker: str, curva: dict):
    if not _db:
        return
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kv_store (key, value, updated_at) VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, (f"volcurve_{ticker}", json.dumps(curva)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        _erro(f"VOL_CURVA_SAVE_ERROR ticker={ticker} error={e}")


def _curva_db_carregar(ticker: str) -> Optional[dict]:
    if not _db:
        return None
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = %s", (f"volcurve_{ticker}",))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


async def curva_sigma(ticker: str) -> Optional[dict]:
    """Curva cacheada: Redis (24h) -> calculo -> kv_store como ultimo recurso."""
    chave = f"volcurve:{ticker}"
    if _redis:
        try:
            bruto = _redis.get(chave)
            if bruto:
                return json.loads(bruto)
        except Exception:
            pass

    curva = await _calcular_curva(ticker)
    if curva:
        if _redis:
            try:
                _redis.setex(chave, _TTL_CURVA, json.dumps(curva))
            except Exception:
                pass
        _curva_db_salvar(ticker, curva)
        return curva

    return _curva_db_carregar(ticker)   # Yahoo fora do ar: usa a ultima boa


# ── Analise ──────────────────────────────────────────────────────────────────

def classificar(z: float) -> str:
    a = abs(z)
    if a < 1.0:
        return "normal"
    if a < 2.0:
        return "acima do normal"
    if a < 3.0:
        return "anormal"
    return "muito anormal"


async def analisar(ticker: str) -> Optional[dict]:
    """Estado atual do ativo com o movimento normalizado pela vol da hora.

    Com o mercado aberto usa o preco ao vivo; fechado, reporta a ultima sessao
    completa. Em ambos os casos o fechamento anterior vem do penultimo bar
    diario -- meta.chartPreviousClose NAO serve: com range=5d ele devolve o
    fechamento de 6 sessoes atras.
    """
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return None

    curva = await curva_sigma(ticker)
    if not curva:
        return None

    d = await _chart(ticker, "1mo", "1d")
    if not d:
        return None
    meta = d.get("meta") or {}
    preco = meta.get("regularMarketPrice")
    dias = _closes(d)
    if not preco or len(dias) < 2:
        return None

    tz = _tz(meta)
    pc = dias[-2][1]                       # fechamento da sessao anterior
    data_ref = str(datetime.fromtimestamp(dias[-1][0], tz).date())

    reg = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    inicio, fim = reg.get("start"), reg.get("end")
    agora = int(datetime.now(timezone.utc).timestamp())
    idx_max = max(int(i) for i in curva)

    if inicio and fim and inicio <= agora <= fim:
        estado = "aberto"
        idx = min(int((agora - inicio) // 3600), idx_max)
    else:
        estado = "fechado"
        idx = idx_max

    sigma = curva.get(str(idx)) or curva[str(idx_max)]
    z = math.log(preco / pc) / sigma if sigma else 0.0

    return {
        "ticker": ticker,
        "nome": meta.get("longName") or meta.get("shortName") or ticker,
        "moeda": meta.get("currency", "USD"),
        "preco": preco,
        "fechamento_anterior": pc,
        "pct": (preco / pc - 1) * 100,
        "z": z,
        "sigma_pct": sigma * 100,
        "idx": idx,
        "estado": estado,
        "data_ref": data_ref,
        "classificacao": classificar(z),
    }


# ── Deduplicacao ─────────────────────────────────────────────────────────────

def deve_alertar(ticker: str, z: float, data_ref: str) -> bool:
    """Um alerta por ativo por sessao; repete so se piorar PIORA_REALERTA sigma.
    Sem isso, um dia ruim geraria um aviso por hora."""
    if abs(z) < LIMIAR_ALERTA:
        return False
    if not _redis:
        return True
    chave = f"vol_alert:{ticker}:{data_ref}"
    try:
        anterior = _redis.get(chave)
        if anterior is None or abs(z) >= float(anterior) + PIORA_REALERTA:
            _redis.setex(chave, _TTL_DEDUP, str(abs(z)))
            return True
        return False
    except Exception:
        return True


# ── Formatacao ───────────────────────────────────────────────────────────────

GUARD = (
    '\n\nINSTRUÇÃO AO ASSISTENTE: repasse os números acima sem qualificar nível nenhum como bom, sólido, forte, gordo, barato, caro, fair value ou zona de compra; sem sugerir comprar, vender, entrar, sair ou esperar; e sem dizer para onde o preço vai. Descreva onde os níveis estão e o que cada um mede. Nada além disso.'
)


def _num(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def formatar_alerta(r: dict, extra: str = "") -> str:
    """Aviso proativo no WhatsApp. `extra` entra antes da ressalva final."""
    seta = "🔺" if r["pct"] > 0 else "🔻"
    hora = "na abertura" if r["idx"] == 0 else f"{r['idx']}h de pregão"
    corpo = (
        f"{seta} {r['ticker']}  {_num(r['pct'])}%  ({_num(abs(r['z']), 1)}σ)\n"
        f"Movimento {r['classificacao']} — σ típico {hora}: {_num(r['sigma_pct'])}%\n"
        f"{r['moeda']} {_num(r['preco'])} (fechamento anterior: {_num(r['fechamento_anterior'])})"
    )
    if extra:
        corpo += f"\n{extra}"
    return corpo + (
        "\n\nIsto é leitura de risco, não recomendação — o movimento é grande "
        "para este ativo, mas não diz nada sobre o que vem depois."
    )


def formatar_modulo(r: dict) -> str:
    """Linha compacta para o relatorio matinal."""
    return (f"{r['ticker']}: {r['moeda']} {_num(r['preco'])} "
            f"({_num(r['pct'])}% | {_num(abs(r['z']), 1)}σ — {r['classificacao']})")


def formatar_analise(r: dict) -> str:
    """Resposta detalhada para a ferramenta do agente."""
    hora = "na abertura" if r["idx"] == 0 else f"após {r['idx']}h de pregão"
    estado = "mercado aberto" if r["estado"] == "aberto" else "mercado fechado, última sessão"
    return (
        f"{r['ticker']} ({r['nome']}) — {estado}\n"
        f"Preço: {r['moeda']} {_num(r['preco'])} | fechamento anterior: {_num(r['fechamento_anterior'])}\n"
        f"Movimento: {_num(r['pct'])}%\n"
        f"σ típico {hora}: {_num(r['sigma_pct'])}% → z = {_num(r['z'], 1)}σ ({r['classificacao']})\n"
        f"Leitura: mede se o movimento é grande para este ativo. "
        f"Não prevê direção futura." + GUARD
    )
