# data_send.py 
# Unified Data Sending Functionality 
# Author: Lily Stacey
# Last Update: 03/10/2025

import paramiko
import json
import asyncio
import logging 

# SSH Config (placeholders)
SSH_HOST = "192.168.1.100"     
SSH_USER = "uavuser"           
SSH_KEY_PATH = "/home/pi/.ssh/id_rsa"  
REMOTE_FILE_PATH = "/home/uavuser/data/air_quality.json"

async def async_send_data( 
        data: dict, 
        remote_path: str, 
        ssh_host: str = SSH_HOST,
        ssh_user: str = SSH_USER,
        ssh_key_path: str = SSH_KEY_PATH
): 
    def _send(): 
        try: 
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname = ssh_host, username = ssh_user, key_filename = ssh_key_path)
            sftp = client.open_sftp()
            with sftp.open(remote_path, 'w') as f: 
                f.write(json.dumps(data))
            sftp.close()
            client.close()
            logging.info(f"Data Sent to {remote_path} on {ssh_host}")
            return True
        except Exception as e: 
            logging.error(f"Failed to send data: {e}")
            return False
    return await asyncio.to_thread(_send)
