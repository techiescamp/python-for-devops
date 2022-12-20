import os
import subprocess

# Script execution without parameters

script_dir = os.path.dirname(__file__)

script_abosulte_path = os.path.join( script_dir + "/files/script.sh")

subprocess.call(['sh', script_abosulte_path])

# Script execution with parameters

param_script_abosulte_path = os.path.join( script_dir + "/files/param.sh")

subprocess.call(['sh', param_script_abosulte_path, 'param1 param2'])







