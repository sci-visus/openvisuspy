import os,sys,glob
for it in glob.glob(sys.argv[1],recursive=True): 
  os.system(f'jupyter trust {it}')
exit()