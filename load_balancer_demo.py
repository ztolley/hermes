"""
FastAPI application with PostgreSQL and Kafka health check.
Requires:
- PostgreSQL connection info in environment variables
- Kafka broker info in environment variables
"""

import os
import psycopg2
from kafka import KafkaProducer, KafkaClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import time

# Configuration from environment variables
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "app")
POSTGRES_USER = os.getenv("POSTGRES_USER", "app")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "test")


class ConnectionStatus(BaseModel):
    service: str
    status: str
    details: dict


app = FastAPI(
    title="PostgreSQL & Kafka Health Check API",
    description="Proves both PostgreSQL and Kafka connections are working",
    version="1.0.0"
)


def get_postgres_connection():
    """Create and return a PostgreSQL connection."""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    return conn


def get_kafka_producer():
    """Create and return a Kafka producer."""
    return KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )


def check_postgres():
    """Test PostgreSQL connection and execute a simple query."""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return {
            "status": "healthy",
            "details": {
                "host": POSTGRES_HOST,
                "port": POSTGRES_PORT,
                "database": POSTGRES_DB,
                "query_test": result[0]
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "details": {"error": str(e)}
        }


def check_kafka():
    """Test Kafka connection and produce a test message."""
    try:
        producer = get_kafka_producer()
        client = KafkaClient(bootstrap_servers=KAFKA_BROKER)
        
        # Check broker connection
        client.ready()
        
        # Produce a test message
        test_msg = {"test": "health_check", "timestamp": time.time()}
        producer.send(KAFKA_TOPIC, test_msg)
        producer.flush()
        producer.close()
        client.close()
        
        return {
            "status": "healthy",
            "details": {
                "broker": KAFKA_BROKER,
                "topic": KAFKA_TOPIC,
                "test_message": test_msg
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "details": {"error": str(e)}
        }


@app.get("/")
def read_root():
    return {"message": "FastAPI with PostgreSQL and Kafka - Health Check API"}


@app.get("/health", response_model=ConnectionStatus)
def health_check():
    """Health check endpoint that tests both PostgreSQL and Kafka connections."""
    postgres_status = check_postgres()
    kafka_status = check_kafka()
    
    overall_status = "healthy"
    if postgres_status["status"] == "unhealthy" or kafka_status["status"] == "unhealthy":
        overall_status = "degraded" if postgres_status["status"] != kafka_status["status"] else "unhealthy"
    
    return {
        "service": "fastapi-postgres-kafka",
        "status": overall_status,
        "details": {
            "postgresql": postgres_status,
            "kafka": kafka_status
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
