import os
import sys

directory = "demodir_"
symbols = "~!@#$%^*()_-+={}[]:>;',</?*-+"
def createDir(dir):
    try:
        if any(char in symbols for char in directory):
            raise ValueError("The directory name contains special characters. Please use only alphabets")
        os.mkdir(dir)
    except ValueError as ve:
        print(ve)
    except OSError:
        print("Folder already Exist. Plese delte it or try with a differnt name")
    createDir(directory)
   
    finally:
        with open("directory.log", "a") as myfile:
        myfile.write("directory creation attempted at %s" % str(datetime.datetime.now()))