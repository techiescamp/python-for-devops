import os
import subprocess

script_dir = os.path.dirname(__file__)

script_abosulte_path = os.path.join( script_dir + "/files/script.sh")

subprocess.call(['sh', script_abosulte_path])

os.system("cat /etc/hosts")
