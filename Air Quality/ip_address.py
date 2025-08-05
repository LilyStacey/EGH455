import requests

def get_public_ip():
    try:
        response = requests.get("https://api.ipify.org") # or "https://checkip.amazonaws.com"
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error getting public IP: {e}"

public_ip = get_public_ip()
print(f"Your Public IP Address: {public_ip}")
