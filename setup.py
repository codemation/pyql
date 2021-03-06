import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
     name='pyql-db',  
     version='PYQLVERSION',
     packages=setuptools.find_packages(include=['pyql'], exclude=['build']),
     author="Joshua Jamison",
     author_email="joshjamison1@gmail.com",
     description="Simple python database orchestration utility which makes it easy to add tables, insert, select, update, delete items with tables",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/codemation/pyql",
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
     python_requires='>=3.4, <4',
     install_requires=['mysql-connector-python'],
 )