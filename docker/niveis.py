"""Niveis de referencia de preco: perfil de volume, pivot points e fundos/topos.

Tudo aqui e DESCRITIVO: diz onde houve negociacao concentrada e onde estao os
extremos recentes. Nenhuma destas medidas preve direcao.

Sobre fundos e topos: a deteccao e fractal com parametros declarados
(JANELA_SWING barras de cada lado + RETRACAO_MIN de retracao). O ponto de fixar
o criterio antes e ser reproduzivel -- parametro diferente da swing diferente, e
isso fica explicito na saida em vez de ser rotulado depois do fato.
"""

import json
import os
from datetime import datetime
from typing import Optional

import vol   # reusa _chart/_closes/_tz para nao duplicar a camada HTTP

# Ajustaveis por env: parametro de swing muda o resultado, entao precisa ser
# trocavel sem rebuild (e fica impresso na saida para nao virar Elliott).
JANELA_SWING = int(os.getenv("NIVEIS_JANELA_SWING", "3"))
RETRACAO_MIN = float(os.getenv("NIVEIS_RETRACAO_MIN", "1.5"))
N_FAIXAS = int(os.getenv("NIVEIS_N_FAIXAS", "40"))
AREA_VALOR = float(os.getenv("NIVEIS_AREA_VALOR", "0.70"))
_TTL_NIVEIS = 21600     # niveis mudam devagar: 6h de cache

_redis = None
_log = None


def configurar(redis_client=None, logger=None):
    global _redis, _log
    _redis = redis_client
    _log = logger


def _erro(msg):
    if _log:
        _log.error(msg)


def _ohlcv(d: dict) -> list:
    """[(epoch, high, low, close, volume)] descartando barras incompletas."""
    ts = d.get("timestamp") or []
    q = ((d.get("indicators") or {}).get("quote") or [{}])[0]
    hi, lo, cl, vo = (q.get("high") or [], q.get("low") or [],
                      q.get("close") or [], q.get("volume") or [])
    out = []
    for i, t in enumerate(ts):
        try:
            h, l, c, v = hi[i], lo[i], cl[i], vo[i]
        except IndexError:
            continue
        if None in (h, l, c) or not v:
            continue
        out.append((t, h, l, c, v))
    return out


# ── Perfil de volume ─────────────────────────────────────────────────────────

def _perfil(barras: list) -> Optional[dict]:
    """Histograma de volume por faixa de preco.

    Dentro de uma barra de 2min nao se sabe como o volume se distribuiu entre
    maxima e minima, entao ele e espalhado uniformemente pela faixa da barra.
    E aproximacao: um perfil tick a tick seria exato, mas exige feed pago.
    """
    if len(barras) < 50:
        return None
    pmin = min(b[2] for b in barras)
    pmax = max(b[1] for b in barras)
    if pmax <= pmin:
        return None

    larg = (pmax - pmin) / N_FAIXAS
    faixas = [0.0] * N_FAIXAS

    for _, h, l, _c, v in barras:
        i0 = max(0, min(N_FAIXAS - 1, int((l - pmin) / larg)))
        i1 = max(0, min(N_FAIXAS - 1, int((h - pmin) / larg)))
        n = i1 - i0 + 1
        for i in range(i0, i1 + 1):
            faixas[i] += v / n

    total = sum(faixas)
    if total <= 0:
        return None

    def centro(i):
        return pmin + larg * (i + 0.5)

    poc_i = max(range(N_FAIXAS), key=lambda i: faixas[i])

    # Area de valor: parte do POC e agrega o vizinho de maior volume
    baixo = alto = poc_i
    acum = faixas[poc_i]
    while acum < total * AREA_VALOR and (baixo > 0 or alto < N_FAIXAS - 1):
        v_ab = faixas[baixo - 1] if baixo > 0 else -1
        v_ac = faixas[alto + 1] if alto < N_FAIXAS - 1 else -1
        if v_ac >= v_ab:
            alto += 1
            acum += faixas[alto]
        else:
            baixo -= 1
            acum += faixas[baixo]

    # Nos de alto volume: faixas com >=70% do volume do POC, fora da area
    hvn = sorted(centro(i) for i in range(N_FAIXAS)
                 if faixas[i] >= faixas[poc_i] * 0.7 and not (baixo <= i <= alto))

    return {
        "poc": centro(poc_i),
        "va_min": pmin + larg * baixo,
        "va_max": pmin + larg * (alto + 1),
        "hvn": hvn[:4],
        "faixa": [pmin, pmax],
        "n_barras": len(barras),
    }


# ── Pivot points ─────────────────────────────────────────────────────────────

def _pivots(h: float, l: float, c: float) -> dict:
    """Pivot classico da sessao anterior. Aritmetica pura, sem ajuste de
    parametro -- nao ha o que sobreajustar aqui."""
    p = (h + l + c) / 3
    return {
        "P": p,
        "R1": 2 * p - l, "S1": 2 * p - h,
        "R2": p + (h - l), "S2": p - (h - l),
        "R3": h + 2 * (p - l), "S3": l - 2 * (h - p),
    }


# ── Fundos e topos ───────────────────────────────────────────────────────────

def _swings(barras: list) -> dict:
    """Fundos e topos fractais: extremo que supera JANELA_SWING barras de cada
    lado, filtrado por RETRACAO_MIN entre swings consecutivos."""
    n = JANELA_SWING
    if len(barras) < 2 * n + 5:
        return {"topos": [], "fundos": []}

    brutos = []
    for i in range(n, len(barras) - n):
        h, l = barras[i][1], barras[i][2]
        viz = range(i - n, i + n + 1)
        if all(h >= barras[j][1] for j in viz if j != i):
            brutos.append((i, "topo", h))
        elif all(l <= barras[j][2] for j in viz if j != i):
            brutos.append((i, "fundo", l))

    # Alterna topo/fundo e exige retracao minima
    limpos = []
    for s in brutos:
        if not limpos:
            limpos.append(s)
            continue
        ult = limpos[-1]
        if s[1] == ult[1]:                       # mesmo tipo: mantem o extremo
            if (s[1] == "topo" and s[2] > ult[2]) or (s[1] == "fundo" and s[2] < ult[2]):
                limpos[-1] = s
            continue
        if abs(s[2] - ult[2]) / ult[2] * 100 >= RETRACAO_MIN:
            limpos.append(s)

    topos = [s[2] for s in limpos if s[1] == "topo"]
    fundos = [s[2] for s in limpos if s[1] == "fundo"]
    return {"topos": sorted(topos)[-5:], "fundos": sorted(fundos)[:5]}


# ── Montagem ─────────────────────────────────────────────────────────────────

async def _calcular_base(ticker: str) -> Optional[dict]:
    intra = await vol._chart(ticker, "1mo", "2m")
    diario = await vol._chart(ticker, "6mo", "1d")
    if not intra or not diario:
        return None

    perfil = _perfil(_ohlcv(intra))
    bd = _ohlcv(diario)
    if not perfil or len(bd) < 20:
        return None

    # Pivot da ultima sessao completa (penultimo bar: o ultimo pode ser parcial)
    _t, h, l, c, _v = bd[-2]
    return {
        "perfil": perfil,
        "pivots": _pivots(h, l, c),
        "swings": _swings(bd),
        "params": {"janela": JANELA_SWING, "retracao_min": RETRACAO_MIN,
                   "faixas": N_FAIXAS, "area_valor": AREA_VALOR},
    }


async def base(ticker: str) -> Optional[dict]:
    chave = f"niveis:{ticker}"
    if _redis:
        try:
            bruto = _redis.get(chave)
            if bruto:
                return json.loads(bruto)
        except Exception:
            pass
    b = await _calcular_base(ticker)
    if b and _redis:
        try:
            _redis.setex(chave, _TTL_NIVEIS, json.dumps(b))
        except Exception:
            pass
    return b


async def analisar(ticker: str) -> Optional[dict]:
    """Niveis + posicao do preco atual em relacao a eles."""
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return None
    b = await base(ticker)
    if not b:
        return None

    d = await vol._chart(ticker, "5d", "1d")
    preco = ((d or {}).get("meta") or {}).get("regularMarketPrice")
    if not preco:
        return None

    p = b["perfil"]
    rotulados = [(f"pivot {k}", v) for k, v in b["pivots"].items()]
    rotulados += [("POC", p["poc"]), ("área valor topo", p["va_max"]),
                  ("área valor base", p["va_min"])]
    rotulados += [(f"nó de volume", v) for v in p["hvn"]]
    rotulados += [("topo", v) for v in b["swings"]["topos"]]
    rotulados += [("fundo", v) for v in b["swings"]["fundos"]]

    acima = sorted([r for r in rotulados if r[1] > preco], key=lambda r: r[1])[:3]
    abaixo = sorted([r for r in rotulados if r[1] < preco], key=lambda r: r[1], reverse=True)[:3]

    if preco > p["va_max"]:
        pos_va = "acima da área de valor"
    elif preco < p["va_min"]:
        pos_va = "abaixo da área de valor"
    else:
        pos_va = "dentro da área de valor"

    return {
        "ticker": ticker, "preco": preco,
        "poc": p["poc"], "va_min": p["va_min"], "va_max": p["va_max"],
        "hvn": p["hvn"], "n_barras": p["n_barras"],
        "pivots": b["pivots"], "swings": b["swings"],
        "pos_va": pos_va, "acima": acima, "abaixo": abaixo,
        "params": b["params"],
    }


# ── Formatacao ───────────────────────────────────────────────────────────────

GUARD = (
    '\n\nINSTRUÇÃO AO ASSISTENTE: repasse os números acima sem qualificar nível nenhum como bom, sólido, forte, gordo, barato, caro, fair value ou zona de compra; sem sugerir comprar, vender, entrar, sair ou esperar; e sem dizer para onde o preço vai. Descreva onde os níveis estão e o que cada um mede. Nada além disso.'
)


def _n(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _dist(preco: float, nivel: float) -> str:
    return f"{abs(nivel / preco - 1) * 100:.1f}".replace(".", ",")


def formatar_contexto(r: dict) -> str:
    """Uma linha para anexar ao alerta de movimento anormal."""
    partes = []
    if r["abaixo"]:
        rot, v = r["abaixo"][0]
        partes.append(f"suporte mais próximo {rot} {_n(v)} (−{_dist(r['preco'], v)}%)")
    if r["acima"]:
        rot, v = r["acima"][0]
        partes.append(f"resistência {rot} {_n(v)} (+{_dist(r['preco'], v)}%)")
    if not partes:
        return ""
    return f"Níveis: {r['pos_va']}; " + "; ".join(partes)


def formatar_modulo(r: dict) -> str:
    """Linha compacta para o relatorio matinal."""
    return (f"{r['ticker']} níveis: POC {_n(r['poc'])} | "
            f"área valor {_n(r['va_min'])}–{_n(r['va_max'])} | "
            f"preço {_n(r['preco'])} ({r['pos_va']})")


def formatar_analise(r: dict) -> str:
    """Relatorio completo para a ferramenta do agente."""
    pv = r["pivots"]
    linhas = [
        f"{r['ticker']} — níveis de referência (preço {_n(r['preco'])})",
        "",
        f"PERFIL DE VOLUME (30d, barras de 2min, {r['n_barras']} barras)",
        f"  POC (maior concentração): {_n(r['poc'])}",
        f"  Área de valor 70%: {_n(r['va_min'])} – {_n(r['va_max'])}",
        f"  Preço está {r['pos_va']}",
    ]
    if r["hvn"]:
        linhas.append("  Nós de alto volume fora da área: " +
                      ", ".join(_n(v) for v in r["hvn"]))
    linhas += [
        "",
        "PIVOT POINTS (sessão anterior)",
        f"  R3 {_n(pv['R3'])} | R2 {_n(pv['R2'])} | R1 {_n(pv['R1'])}",
        f"  P  {_n(pv['P'])}",
        f"  S1 {_n(pv['S1'])} | S2 {_n(pv['S2'])} | S3 {_n(pv['S3'])}",
        "",
        f"FUNDOS E TOPOS (6 meses, diário, janela {r['params']['janela']} barras, "
        f"retração mín {_n(r['params']['retracao_min'])}%)",
        "  Topos: " + (", ".join(_n(v) for v in r["swings"]["topos"]) or "nenhum"),
        "  Fundos: " + (", ".join(_n(v) for v in r["swings"]["fundos"]) or "nenhum"),
        "",
        "MAIS PRÓXIMOS",
    ]
    for rot, v in r["acima"]:
        linhas.append(f"  ↑ {rot} {_n(v)} (+{_dist(r['preco'], v)}%)")
    for rot, v in r["abaixo"]:
        linhas.append(f"  ↓ {rot} {_n(v)} (−{_dist(r['preco'], v)}%)")
    linhas += [
        "",
        "Leitura: são níveis onde houve negociação concentrada ou extremos recentes. "
        "Servem de referência para enquadrar o preço atual. Nenhum deles prevê "
        "direção — swing depende da janela escolhida, e pivot é aritmética da "
        "sessão anterior, não sinal.",
    ]
    return "\n".join(linhas) + GUARD
