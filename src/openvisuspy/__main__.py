import os, sys

this_dir=os.path.dirname(os.path.abspath(__file__))

# //////////////////////////////////////////
if __name__ == "__main__":
  if len(sys.argv)>=2 and sys.argv[1]=="dirname":
    print(this_dir)
    sys.exit(0)
