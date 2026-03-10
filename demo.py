"""Demo script to call the LLM API using the client."""
from dotenv import load_dotenv
load_dotenv()


import asyncio
from src.schemas import DecisionRequest
from src.services.llm_client import LLMClient


demo_request = DecisionRequest(
    domain="anomaly",
    data=[
        {
            "model_state": {"mse": 0.0023},
            "model_output": {
                "latency_mean": 145.2,
            },
        }
    ],
    decisions=[
        "scale_up",
        "redirect_traffic",
        "apply_qos_policy",
        "alert_noc",
        "do_nothing",
    ],
)


async def main():
    client = LLMClient()

    print("=== Client Info ===")
    info = client.info()
    for k, v in info.items():
        print(f"  {k}: {v}")

    print("\n=== Request ===")
    payload = client._prepare_request(demo_request)
    print(f"  Model: {payload['model']}")
    print(f"  Prompt:\n{payload['prompt']}")

    print("\n=== Calling LLM... ===")
    response = await client.query(demo_request)
    print("\n=== Response ===")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
