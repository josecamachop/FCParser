from setuptools import setup

setup(name='fcparser',
      version='1.0',
      description='Feature as a counter parser',
      url='https://github.com/josecamachop/FCParser',
      author='Alejandro Perez Villegas, Jose Manuel Garcia Gimenez',
      author_email='alextoni@gmail.com, jgarciag@ugr.es',
      license='GPLv3',
      packages=['fcparser','deparser'],
      install_requires=[
          'IPy', 'pyyaml'
      ],
      zip_safe=False)
