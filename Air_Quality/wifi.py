import psutil

def get_network_interface_stats():
    """
    Returns statistics for all network interfaces.
    """
    return psutil.net_if_stats()

stats = get_network_interface_stats()
for interface, data in stats.items():
    print(f"Interface: {interface}, Is Up: {data.isup}, Speed: {data.speed} Mbps")