# FCParser User Manual



## 1. OVERVIEW

Raw data is not suitable for statistical analysis, parsing the data is needed in order to obtain
observations for further analysis.
FCparser is a tool that provides a comfortable, general and highly configurable parsing of network data
originating from different sources. It has been designed to transform large amounts of heterogeneous network data into a
single matrix of data observations suitable for multivariate analysis, without losing
relevant information in the process. Also, it provides the opposite process of parsing:
_deparsing._ Using both detection and diagnosis information, the original raw data
records related to anomaly are identified and presented to the analyst.


## 2. PARSER

The parser transform heterogeneous data into observations arrays. This program is
designed to take any text based file as input, alongside general configuration file
and configuration files appropriately customized for each data source.
Data sources, such as logs from network and security related programs, have an uneven format.
They can be structured (e.g _csv_ files) or unstructured (e.g one log entry each paragraph).
With expertise in regular expressions, both of them can be handled with this parsing approach.

Feature as a counter ( _FaaC_ ) is the algorithm chosen to generate observations. Each
feature contains the number of times a given event (e.g the apparition of a word in a log
file) takes place. This general definition makes it possible to handle most data sources
[1].

To provide flexibility to the tool, observation can be grouped to specific criteria. This is
called aggregation (e.g aggregate observation by source IP) and it is defined in general configuration file.

<p align="center"> <img width="700" height="418" src="assets/block_diagram.png"> </p>
<div align="center"><i>Figure 1: Block diagram of the parser</i></div><br /> 

Temporal sampling is an optional process included in the parsing program. This
procedure is performed by splitting input files into smaller files, each of those contains
log entries from a specific time window. Time window and other splitting parameters
are defined in the general configuration file as well.

The program generates one file for each observation following this naming scheme:
_output-yyyymmddhhmm.dat._ Those files contain the observation array and aggregation
keys if they are used. Also, the program generates a header file with a list feature names and a stats
file. The directory where these files are saved is defined in the general configuration
file.

### 2.1. GENERAL CONFIGURATION FILE

The program is fully configurable using only configuration files. These files are in
YAML (YAML Ain't Markup Language) format. YAML is a human friendly data
serialization standard for all programming languages. For python, YAML files are
loaded as nested dictionaries depending on the indentation.  
In FCParser, there are two kinds of configuration files: <ins>general configuration file</ins> and
<ins>data sources configuration files</ins>.

The General configuration file contains the main information for the parsing process:
datasources, aggregation keys, output directories and split configuration. An empty
general configuration file look like this:

<p align="center"> <img width="704" height="550" src="assets/general_configuration.png"> </p>
<div align="center"><i>Figure 2: General configuration file [configuration.yaml]</i></div><br />

**DataSources**: In this field, different data sources must be specified. For each data
source, the name, the specific configuration file for that data source and the data path have to
be specified. Input data can be in _csv_ format, text based log files or _nfcapd_ binary data.

**Keys:** In this field, none, one or more aggregation keys are defined. These keys are the
variables chosen to aggregate observation. For each unique value of said keys,
conservation are grouped (e.g source IP: for each unique value of source ip one observation of features is generated). Aggregation keys must be variables from the data sources. If the chosen aggregation key is not a variable for a data source, that data
source won’t be parsed. If the field is empty, aggregation will not occur, so it is analyzed by timestamp.

**Online**: Boolean variable to determine if online or offline mode. Online mode is set for real time application
              (only one process) while offline mode is used for processing already stored data sets (multiprocess).

**Processes**: Number of processes used by the program. Use a number between 1 and the number of cores of your system.

**Split:** In this field, the temporal sampling parameters are specified. Time window in
minutes, as well as start time and end time for sampling interval. Time parameters format must be YYYY-MM-DD hh:mm:ss.
If no time window is defined, 5 minutes is considered as default value.

<p align="center">-Parsing parameters-</p>

**Parsing_Output:** In this field, the output directory for the parsed data and the stats file (which contains lines, records, matches) and weights file
are defined. Headers.dat (containing a list of feature names) and weights.dat files are generated by default if no names are specified.

**Incremental_output**: Boolean variable for incremental features. If true and output files exist, new counters are added to the old ones.

**Max_chunck**: Size (in megabytes) of the chunk of files that are being processed at the same time.

<p align="center">-Deparsing parameters-</p>

**Deparsing_output:** In this field the output directory for the _deparsed_ raw data and the
stats file are defined. This configuration is only used for _deparsing_ process.

**Threshold:** The upper limit of log entries by datasource can be specified in the threshold parameter.

<p align="center">-Learning parameters-</p>

**Lperc/Endlperc**: Proportion (percentage) of data used for learning.

### 2.2. DATA SOURCES CONFIGURATION FILES

Data sources configuration files are designed to easily adapt different data sources to the
program without knowledge of the internal programing. They are located in the same directory along the general configuration file.

The structure of these configuration files is shown in Figure 3:

<p align="center"> <img width="600" height="643" src="assets/data_source_configuration.png"> </p>
<div align="center"><i>Figure 3: Data Source configuration file</i></div><br />

**<ins>Attributes:</ins>**

- _Tag_: Key to identify data source, it is recommended to use simple tags (e.g _fw_
    for firewall).
- _Structured_: boolean variable to identify if a source is structured or unstructured.
- _Timestamp_format_: timestamp format for the logs in the files of the data source
    in python datetime format [2].
- _Separator_: Char that delimits the log entries of the source. It is mandatory for unstructured sources while for structured sources /n is considered if none is specified.
- _Timearg_: Timearg is the name of the timestamp variable.

**<ins>Variables:</ins>** Variables are fields that are extracted from a log entry (e.g source ip,
destination port, etc). Variables attributes differ depending if the data source is
structured or not, but the skeleton remains the same.
For structured sources, raw data is extracted from a determined position (e.g fourth field of a _csv_ entry).
For unstructured source, fields are extracted with regular expressions.

- _Name_: Variable name chosen by the user.
- _Matchytype_ is the type of the field extracted (string, number, ip, time or duration).
  For structured sources, it is the type of the raw data extracted, whereas for unstructured sources,
  _matchtype_ is the type of the match for the regular expression.
- _Where_ is the key to find the field. It is the position of the field in the line (first position corresponds
  to zero value) for structured sources, while for unstructured sources it is the regular expression that match the wanted
field.

A clear explanation of these variable fields can be found in the Example section.

Note: There must be a variable (whose name is defined in timearg atrribute) which collects the timestamps, and it must be defined as time matchtype.

**<ins>Features:</ins>** Based on the defined variables, different features are specified in order to be considered afterwards during multivariate analysis. For instance, if a variable src_port is extracted from logs, multiple features can be created depending on the value of that variable. Thus, we might have features such as port_http, port_ssh or port_smtp if the value of the variable src_port in logs matches 80, 22 or 25, respectively.
Thus, some fields must be specified:
- _Name_: Feature name chosen by the user.
- _Variable_: Name of the variable from which the feature is calculated.
- _Matchtype_: Kind of association between the variable and the feature:
    - _Single_: The feature is defined for a specific value of the variable.
    - _Multiple_: When multiple values of a variable match the same feature.
    - _Range_: The feature is represented by all the values within a specific range.
    - _Default_: Useful for considering different values than those previously defined. So, value field will be empty for this case.
    - _Regexp_: It is used when dealing with unstructured sources. Value field will match a certain string.
- _Value_: Depending on the matchtype field, one or more values will be defined. Value is empty if matchtype is default.
- _Weight_: Optional parameter to assign different weights to the features. It might be useful for deparsing process.
If weight is not specified for a feature, it is automatically set to one.

Note: A script creatconf.py is also given in config directory in order to build a FCParser config file for a data source out of a json with counts. This is useful to automatically decide the features of the system. Also, fclearning in bin directory.


## 3. DEPARSER

Using both detection and diagnosis information, the original raw data records related to
anomaly are identified and presented to the analyst. This process is called _deparsing_ and
it is a straight forward process, that reduce the challenge of searching logs, surgically
extracting data related to anomalies.

The program uses the same configuration files that the parser and reverse the parsing
criteria. It takes as input a list of timestamps and a list of features, and outputs a file of
log entries that contains those features and occurred in those timestamps.
To delimit the amount of log entries extracted, there is a threshold of log entries that are
extracted. Log entries that contain more selected features are prioritized. However, this
threshold is not absolute and log entries with the same amount of features should not be
dismissed. For this reason, the threshold is checked after processing an entire block of
log entries with the same number of features appearances.

The input file format is adapted to the output of the MEDA-Toolbox [3]. This toolbox is
a tool that can be used to analyze the parsed data. The format of the _deparsing_ input
file look like this:

<p align="center"> <img width="650" height="247" src="assets/deparsing.png"> </p>
<div align="center"><i>Figure 4: Format of deparsing input file</i></div><br />


## 4. EXAMPLE

### 4.1. PARSING

An example with structured and unstructured sources can be found in the FCParser _example_ directory.
For this example, data sources are _netflow_ (structured data, in _csv_ file) and _ids_ logs (unstructured log entries, where one log each entry consists of a paragraph).

Fig. 5 shows the general configuration file for this example.  
<p align="center"> <img src="assets/example_general_config.png"> </p>
<div align="center"><i>Figure 5: Example - General configuration file</i></div><br />


In the upper part, the different data sources are specified (netflow and IDS), including the data directory and the path where data source configuration file is located. Keys field is unused, aggregation is not performed and observations will then be grouped by timestamp.
At the end of the file, there is the configuration for temporal sampling. In this case, the sampling rate is one minute.

Let's now see what the data looks like so that we can specify the configuration files for these data sources.
So, for netflow data, we can find the data file (nf.csv) in Examples_data directory and netflow configuration file in the config directory (netflow.yaml). If we take a look at the data, it consists of comma separated values where every line is an entry.

An example of the structure of some entries (lines) is depicted in Figure 6:  

![](assets/example_netflow_data.png)
<div align="center"><i>Figure 6: Example - Netflow datasource</i></div><br />
Based on this structure, we can create our data source configuration file, where the attributes, variables and features will be defined according to our goals:<br />  


<p align="center"> <img width="500" height="613" src="assets/example_netflow_config.png"> </p>
<div align="center"><i>Figure 7: Example - Netflow configuration file</i></div><br />
In figure 7, we can see a fragment of the configuration file for a _netflow_ data source.
It shows the mandatory attributes for structured sources. As we mentioned before, timearg attribute represents the instant at which a certain event occurred, and it is defined by means of the timestamp variable. The _where_ value of the timestamp variable (zero) matches the position in the entry line (the first column of every entry in data log corresponds with the time instant). Timestamp format is also specified according to the data file.<br />  
For more information about the timestamp format, check: https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior

<br />In the case of IDS data source, the data file in Examples_data directory is named _ids.log_ and IDS configuration file in the config directory is named _ids.yaml_.

In Figure 8, we can see an example of unstructured data, where each log entry consists of a paragraph.
<p align="center"> <img width="800" height="367" src="assets/example_ids_data.png"> </p>
<div align="center"><i>Figure 8: Example - IDS log entries</i></div><br />


In Figure 9, an unstructured source configuration file is depicted, where some variables and features are defined using regular expressions. When building the IDS configuration file, the mandatory attributes differ from those ones in netflow configuration file (structured source) as, for these kind of sources, regular expressions are needed to extract the data. These regular expressions are used to search variables in the log entries.
<p align="center"> <img width="900" height="620" src="assets/example_ids_config.png"> </p>
<div align="center"><i>Figure 9: Example - IDS configuration file</i></div><br />

For this case, it is necessary to define the separator between entries (two blank lines). We can also see how regular expressions are used to define the variables, including the timestamp variable. Some features are also depicted in the figure, for which differents weights are assigned. Using these weight values will be useful for the deparsing process.


In order to run the example and parse the data, just run the following command in the FCParser directory:

    $ python bin/fcparser.py example/config/configuration.yaml

<p align="center"> <img width="400" height="288" src="assets/example_parser.png"> </p>
<div align="center"><i>Figure 10: Example - Parsing data</i></div><br />

The parser output consists of:
- The stats file, which includes number of variables, log entries and size in bytes:
<p align="center"> <img width="415" height="250" src="assets/example_stats.png"> </p>

- The header file, with a list of the features from all data sources:
<p align="center"> <img width="700" height="285" src="assets/example_headers.png"></p>
  Where the 143 ids feature names are concatenated after the 142 netflow feature names.</p>

- The weights file, which includes the weight associated to each feature. If a feature has no weight defined in configuration file, weight is automatically set to one, as depicted in the next figure:
<p align="center"> <img width="700" height="276" src="assets/example_weights.png"> </p>

- The parsed data with the timestamp in the file name (output-yyyymmddhhmm.dat).
As time window was set to one minute, the number of files generated will match the number of minutes for which we have records.

The structure of these files look as depicted:
<p align="center"> <img width="700" height="171" src="assets/example_output.png"> </p>
Where the number of times a given event (feature) occurs is recorded as comma-separated values, for each of the 285 features.


### 4.2. DEPARSING

The _deparsing_ process uses the same configuration files used before. Using both
detection and diagnosis information, the original raw data records related to anomaly
are identified and presented to the analyst. Detection and diagnosis information is
specified in the _deparsing_ input file.

An example of deparsing input file is depicted in figure 11:
<p align="center"> <img width="390" height="320" src="assets/example_deparsing_input.png"> </p>
<div align="center"><i>Figure 11: Example - Deparsing input file</i></div><br />

To run the program, use the following command:

	$ python bin/fcdeparser.py example/config/configuration.yaml example/deparsing_input

The _deparsing_ program generates one file for each data source with the extracted logs
related to the anomalies detected, as well as stats file with the number of structured and unstructured logs deparsed.

<p align="center"> <img width="800" height="323" src="assets/example_deparsing_output.png"> </p>
<div align="center"><i>Figure 12: Example - Deparsing output</i></div><br />


## 5. INSTALLATION REQUIREMENTS

FCParser is designed to work on UNIX system with python installed. Almost every
linux distribution come with python pre-installed. For library compatibility, python 3 is the required version.
If you are using an older version of Python, you might update your Python libraries or create a Python3 virtual environment using virtualenv, for example:

	$ virtualenv --python=python3 FCParser/env
	$ source FCParser/env/bin/activate

The program requires some python modules to work properly. Before using this tool,
install the following packages:

- Ipy – Python module for handling _IPv4_ and _IPv6_ addresses and networks [4]
    ```
    $ pip install IPy
    ```
- PyYAML – _YAML_ analyzer for python [5].
    ```
    $ pip install PyYAML
    ```
Nfdump [6]_._ In order to work with _netflow_ data in _nfcapd_ format, the _netflow_ processing
tool _Nfdump_ is required.


## REFERENCES

[1] Camacho, José & Pérez-Villegas, Alejandro & García-Teodoro, Pedro & Maciá-
Fernández, Gabriel. (2016). PCA-based multivariate statistical network monitoring for
anomaly detection. Computers & Security. 59.. 10.1016/j.cose.2016.02.008.

[2] Python datetime module for manipulating dates and times. Available at:
https://docs.python.org/2/library/datetime.html

[3] Camacho, J., Pérez, A., Rodríguez, R., Jiménez-Mañas, E. Multivariate Exploratory
Data Analysis (MEDA) Toolbox. Chemometrics and Intelligent Laboratory Systems,
2015, 143: 49-57, available at: https://github.com/josecamachop/MEDA-Toolbox

[4] _IPy_ , python module for handling of IPv4 and IPv6 addresses and networks.
Available at: https://pypi.python.org/pypi/IPy/

[5] _PyYAML_ , The next generation _YAML_ parser and emitter for Python. Available at:
https://pypi.python.org/pypi/PyYAML

[6] _NFDUMP_ , tools to collect and process _netflow_ data on the command line. Available
at: [http://nfdump.sourceforge.net/](http://nfdump.sourceforge.net/)


