import json
import os
import boto3
import psycopg2
from datetime import datetime

ORACLE_VM_IP = os.environ['ORACLE_VM_IP']
POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

sns = boto3.client('sns')

def get_db_connection():
    return psycopg2.connect(
        host=ORACLE_VM_IP,
        database="personal_kb",
        user="assistant",
        password=POSTGRES_PASSWORD,
        port=5432
    )

def check_reminders():
    """Verifica lembretes que precisam ser disparados"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, description
        FROM reminders
        WHERE trigger_time <= NOW()
        AND triggered = FALSE
    """)
    
    reminders = cur.fetchall()
    
    for reminder_id, title, description in reminders:
        # Enviar notificação
        send_notification(title, description)
        
        # Marcar como disparado
        cur.execute("""
            UPDATE reminders
            SET triggered = TRUE
            WHERE id = %s
        """, (reminder_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return len(reminders)

def send_notification(title, message):
    """Envia notificação via SNS"""
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=title,
            Message=message,
            MessageStructure='json',
            Message=json.dumps({
                'default': message,
                'APNS': json.dumps({
                    'aps': {
                        'alert': {
                            'title': title,
                            'body': message
                        },
                        'sound': 'default'
                    }
                })
            })
        )
        print(f"Notification sent: {title}")
    except Exception as e:
        print(f"Error sending notification: {str(e)}")

def handler(event, context):
    """Handler para verificar e enviar notificações"""
    try:
        reminders_sent = check_reminders()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'reminders_sent': reminders_sent
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
