
import os,sys, tomli

# ////////////////////////////////////////////////////////////
if __name__=="__main__":
	
	with open("pyproject.toml", "rb") as f: 
		config = tomli.load(f)
	
	old_version=config['project']['version']
	v=old_version.split('.')
	new_version=f"{v[0]}.{v[1]}.{int(v[2])+1}"
	
	with open("pyproject.toml", "rt") as f: 
		lines = f.readlines()

	# version = "1.0.36"
	lines=[(f'version = "{new_version}"\n' if line.startswith("version =") else line) for line in lines]

	body="".join(lines)
	# print(body)
	
	with open("pyproject.toml", "wt") as f: 
		f.write(body)
	
	print(new_version)
	sys.exit(0)