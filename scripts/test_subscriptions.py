#!/usr/bin/env python3
"""Test script for subscriptions system.

Usage:
    # Start a simple callback server to receive notifications
    python scripts/test_subscriptions.py server

    # Subscribe to events for specific cells
    python scripts/test_subscriptions.py subscribe --cells 1 2 3 --events forecast anomaly

    # List current subscriptions
    python scripts/test_subscriptions.py list

    # Delete a subscription
    python scripts/test_subscriptions.py delete <subscription_id>
"""

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

DECISION_API = os.getenv("DECISION_API", "http://localhost:8000/api/v1")


class CallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to receive and print notifications."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
            print("\n" + "=" * 60)
            print("NOTIFICATION RECEIVED")
            print("=" * 60)
            print(json.dumps(data, indent=2))
            print("=" * 60 + "\n")
        except json.JSONDecodeError:
            print(f"Received non-JSON: {body}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def run_callback_server(port: int = 9999):
    """Run a simple HTTP server to receive notifications."""
    server = HTTPServer(("0.0.0.0", port), CallbackHandler)
    print(f"Callback server listening on http://0.0.0.0:{port}")
    print("Waiting for notifications...\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down callback server")
        server.shutdown()


def subscribe(cells: list[int], events: list[str], callback_url: str):
    """Create a subscription."""
    payload = {
        "callback_url": callback_url,
        "cell_ids": cells,
        "event_types": events,
    }

    print("Creating subscription:")
    print(f"  Cells: {cells}")
    print(f"  Events: {events}")
    print(f"  Callback: {callback_url}")

    response = httpx.post(f"{DECISION_API}/subscriptions", json=payload)

    if response.status_code == 201:
        data = response.json()
        print("Subscription created!")
        print(f"  ID: {data['id']}")
        print(f"  Created at: {data['created_at']}")
    else:
        print(f"\nError: {response.status_code}")
        print(response.text)


def list_subscriptions():
    """List all subscriptions."""
    response = httpx.get(f"{DECISION_API}/subscriptions")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {data['count']} subscription(s):\n")
        for sub in data["subscriptions"]:
            print(f"  ID: {sub['id']}")
            print(f"    Callback: {sub['callback_url']}")
            print(f"    Cells: {sub['cell_ids']}")
            print(f"    Events: {sub['event_types']}")
            print(f"    Created: {sub['created_at']}")
            print()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


def delete_subscription(subscription_id: str):
    """Delete a subscription."""
    response = httpx.delete(f"{DECISION_API}/subscriptions/{subscription_id}")

    if response.status_code == 200:
        print(f"Subscription {subscription_id} deleted")
    elif response.status_code == 404:
        print(f"Subscription {subscription_id} not found")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


def main():
    parser = argparse.ArgumentParser(description="Test subscriptions system")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    server_parser = subparsers.add_parser("server", help="Run callback server")
    server_parser.add_argument(
        "--port", type=int, default=9999, help="Port to listen on"
    )

    # Subscribe command
    sub_parser = subparsers.add_parser("subscribe", help="Create subscription")
    sub_parser.add_argument(
        "--cells", type=int, nargs="+", required=True, help="Cell IDs"
    )
    sub_parser.add_argument(
        "--events", type=str, nargs="+", required=True, help="Event types"
    )
    sub_parser.add_argument(
        "--callback", type=str, default="http://localhost:9999", help="Callback URL"
    )

    # List command
    subparsers.add_parser("list", help="List subscriptions")

    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete subscription")
    del_parser.add_argument("id", type=str, help="Subscription ID")

    args = parser.parse_args()

    if args.command == "server":
        run_callback_server(args.port)
    elif args.command == "subscribe":
        subscribe(args.cells, args.events, args.callback)
    elif args.command == "list":
        list_subscriptions()
    elif args.command == "delete":
        delete_subscription(args.id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
