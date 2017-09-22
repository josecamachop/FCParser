
# FCParser


## Presentation


The FaaC parser library allows a comfortable, general and highly configurable parsing
of network data originating from different sources. It has been designed to transform
large amounts of heterogeneus network data into a single matrix of data observations
suitable for multivariate analysis, without losing relevant information in the process.

The parsing process performs mainly 3 actions over the data:

1. CONVERT variables into observatios of features to facilitate the further analysis. In this case, 
features work as a counter (FaaC, feature as a couter).
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
split setting. See /config/configuration.yaml for more info. There are example configuration 
files in Example directory.

2.- Split data (otpional). Usually, sampling the input data is required.
The sampling configuration and datasources are defined in configuration.yaml. 
If split parameters are not determined, the data won't be sampled.

3.- Parse data. Extract observations from data.

In the example, data is sampled every 60s. Example usage:

	$ python parser/parser.py Example/config/configuration.yaml 

### Deparsing

1.- Configuration. The deparsing program use the same configuration file used in parsing 
process, see /config/configuration.yaml for more info.

2.- Deparsing. Extract the logs related to anomalies. It takes as input features and timestamps.
See Example to see format of the file.

	$ python deparser/deparser.py Example/config/configuration.yaml Example/deparsing_input 


## Installation Requirements

faaclib requires some python libraries to work properly. Before using this tool,
install the following packages:

- IPy - Python module for handling IPv4 and IPv6 addresses and networks
	$ pip install IPy

- PyYAML - YAML analyzer for Python
	$ pip install PyYAML


## Summary

The present repository is organized as follows:

- parser/ 		          Python Module with all of the lib classes and main script to parser process.
- deparser/               Python script for deparsing process.
- config/                 Empty configuration files. 
- Example/		          Data and configuration for an example example.
	- Examples_data       Structured and unstructured data to test the tool.
	- config 			  Configuration files adapted to the provided data.


