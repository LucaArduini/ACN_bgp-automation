import jinja2
import os
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")


environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR)
)

template = environment.get_template("config.j2")


device = {
    "hostname": "CE2",
    "dhcp_server": False,
    "bgp": {
        "asn": 65000,
        "router_id": "10.0.0.1",
    }
}

intf = [
	{
        "name": "eth0", 
        "switch": 1,
        "dhcp": "false",
        "ipv4_address": "172.0.0.1"
    },
	{
        "name": "eth5", 
        "dhcp": "false",
        "ipv4_address": "172.0.0.2"
    },
]
	
content = template.render(
	interfaces=intf,
    device=device
)

print(content)