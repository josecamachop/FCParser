
# FCParser

Parser for data streams composed of variate (structured and unstructured) sources.

Contact persons: José Camacho Páez (josecamacho@ugr.es)

Last modification of this document: 10/Jul/18


## Presentation

The FaaC parser library allows a comfortable, general and highly configurable parsing
of network data originating from different sources. It has been designed to transform
large amounts of heterogeneus network data into a single time-resolved stream of data
features suitable for the analysis with multivariate techniques and other machine 
learning tools, hopefully without losing relevant information in the process.

The parsing process performs mainly 3 actions over the data:

1. CONVERT variables into observatios of features to facilitate the further analysis. In this case, features work as a counter (FaaC: Feature as a Counter).
2. AGGREGATE observations according to specific criteria.
3. FUSE observations from different datasources.
   
To reach these goals, the analyst must provide expert knowledge on the data she wants
to analyze. The analyst must decide which datasources include, which information is
relevant, which criteria use for the aggregation and define the output features.  
To this end, FaaC parser library is highly configurable. All this setup is easily configurable
through configuration files in YAML format. These files can be found in the 'config'
folder. The format of the config files is explained in the beggining of each file.

																						
## Getting Started
														
### Parsing

1.- Configuration. First step is generate configuration.yaml according to datasources and 
split setting. See /config/configuration.yaml for more info. There are some example configuration 
files in the example directory.

2.- Split data (optional). Usually, sampling the input data is required.
The sampling configuration and datasources are defined in configuration.yaml. 
If split parameters are not determined, the data won't be sampled.

3.- Parse data. Extract observations from data.

In the example, data is sampled every minute. Example usage:

	$ python bin/fcparser.py example/config/configuration.yaml 

### Deparsing

1.- Configuration. The deparsing program use the same configuration file used in parsing 
process, see /config/configuration.yaml for more info.

2.- Deparsing. Extract the logs related to anomalies. It takes as input features and timestamps.
See the example to see format of the file.

	$ python bin/fcdeparser.py example/config/configuration.yaml example/deparsing_input 


## Installation

#### Dependencies

The *faac* library requires some extra python libraries to work properly. They are:

- IPy - Python module for handling IPv4 and IPv6 addresses and networks
- PyYAML - YAML analyzer for Python

Both dependencies can be installed using pip:

	$ pip install IPy PyYAML 

#### Python version

Python3 is required to run this programme.
If you are using an older version of Python, you might update your Python libraries or
create a Python3 virtual environment using virtualenv, for example:

	$ virtualenv --python=python3 FCParser/env
	$ source FCParser/env/bin/activate 


## Summary

The present repository is organized as follows:

- assets/			Figures used in FCParser user manual.
- bin/				Python Modules with all of the lib classes and main scripts to parser and deparser process.
- config/			Directory for configuration files. It contains empty configuration files as template.
- example/			Data and configuration files for example
	- config:			Configuration files adapted to the provided data.
	- deparsing_input:	  	Input file containing selected features and timestamps for deparsing process.
	- deparsing_output:	  	Output directory for deparsing process.
	- Examples_data:      		Structured and unstructured data to test the tool.
	- OUTPUT:			Output directory containing parsed example data.
