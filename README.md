
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


1.- Configuration. First step is generate configuration.yaml according to datasources and 
split setting. See /config/configuration.yaml for more info. Configuration files are 
set for example data by default.


2.- Split data (otpional). Usually, sampling the input data is required, for this task, the 
script splitData.py is used. The sampling configuration and datasources are defined 
in configuration.yaml. Example:

	$ python scripts/splitData.py config/configuration.yaml 

3.- Parse data. Extract observations of features from sampled data. 
Example usage:

	$ python parser.py config/configuration.yaml 



## Installation Requirements

faaclib requires some python libraries to work properly. Before using this tool,
install the following packages:

- IPy - Python module for handling IPv4 and IPv6 addresses and networks
	$ pip install IPy

- PyYAML - YAML analyzer for Python
	$ pip install PyYAML


## Summary

The present repository is organized as follows.
- faaclib.py    Python Module with all of the API classes.
- parser.py        Main script to run FlowParser.
- config/          Example of configuration files for the parser and for several datasources.
- scripts/         Scripts used to preprocess and prepare the data before the parsing.
- Examples_data/   Data for example configuration.




