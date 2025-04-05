# test script to check that the endpoint is up.
import requests
from dotenv import load_dotenv
import os

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

url = "https://integrate.api.nvidia.com/v1/chat/completions"

payload = {
    "model": "google/gemma-3-27b-it",
    "messages": [
        {
            "content": "I am going to Paris, what should I see?",
            "role": "user"
        }
    ],
    "temperature": 0.2,
    "top_p": 0.7,
    "max_tokens": 1024,
    "seed": 42,
    "stream": False,
    "stop": ["string"],
    "bad": ["string"]
}
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": f"Bearer {NVIDIA_API_KEY}"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)