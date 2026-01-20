import jinja2
import os
import yaml
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")

data_path = os.path.join(TOPOLOGY_DIR, "data.yaml")
output_path = os.path.join(TOPOLOGY_DIR, "network.clab.yml")

environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR)
)

template = environment.get_template("topology.j2")

with open(data_path, 'r') as f:
    data = yaml.safe_load(f)

#TODO do some checks on input file

with open(output_path, 'w') as f:
    f.write(template.render(nodes=data['nodes'], links=data['links']))

print("Container lab network yaml file generated!")