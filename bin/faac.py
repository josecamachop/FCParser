"""

FaaC parser library -- classes and tools for parsing and processing raw network
data and preparing it for further multivariate analysis.

See README file to learn how to use FaaC parser library.

Authors: Alejandro Perez Villegas (alextoni@gmail.com)
	 Jose Manuel Garcia Gimenez (jgarciag@ugr.es)
	 Jose Camacho (josecamacho@ugr.es)	

Last Modification: 11/Aug/2018

"""

from datetime import datetime, timedelta
from IPy import IP
import time
import re
import os
import yaml
import glob


#-----------------------------------------------------------------------
# Variable Class
#-----------------------------------------------------------------------

class Variable(object):
	"""Single piece of information contained in a raw record.
	
	This is an abstract class, and should not be directly instantiated. 
	Instead, use one of the subclasses, defined for each matchtype of variable:
	- StringVariable    (matchtype 'string')
	- NumberVariable    (matchtype 'number')
	- IpVariable        (matchtype 'ip')
	- TimeVariable      (matchtype 'time')
	- TimedeltaVariable (matchtype 'duration')
	- MultipleVariable  (matchtype 'multiple')
	
	Class Attributes:
		value -- The value of the variable.
	"""
	def __init__(self, raw_value):
		"""Class constructor.

		raw_value -- Single value, as it is read from the input.
		"""
		self.value = self.load(raw_value)

	def equals(self, raw_value):
		"""Compares this variable to a given value.
		Returns 1 if the comparison matches; 
		        0 otherwise.

		raw_value -- The value to compare with.
		"""
		value = self.load(raw_value)
		output = (self.value == value)
		if output:
			return 1
		else:
			return 0

	def belongs(self, start, end):
		"""Checks whether this variable belongs to an interval.
		Returns 1 if the variable's value belongs to the interval;
		        0 otherwise.
		
		start -- Initial value of the interval (inclusive).
		end   -- Final value of the interval (inclusive).
		         'None' value means infinite.
		"""
		start_value = self.load(start)
		end_value   = self.load(end)

		if self.value is None or start_value is None:
			output = False
		elif end_value is None:
			output = (self.value >= start_value)
		else:
			output = (self.value >= start_value and self.value <= end_value)

		return output
		

	def __repr__(self):
		"""Class default string representation.
		"""
		return self.value.__str__()


class StringVariable(Variable):
	"""Variable containing an alphanumeric value.
	"""
	
	def load(self, raw_value):
		"""Converts an input raw value into a string object.
		Returns: String, if the conversion succeeds;
		         None, if the string is empty or the conversion fails.

		raw_value -- The input raw value.
		"""
		if raw_value:
			try:
				value = str(raw_value).strip()
				if not value:
					value = None
			except:
				value = None
		else:
			value = None
		return value


class NumberVariable(Variable):
	"""Variable containing a number.
	"""

	def load(self, raw_value):
		"""Converts an input raw value into an integer number.
		Returns: Integer number, if the conversion succeeds;
		         None, if the conversion fails.

		raw_value -- The input raw value.
		"""
		try:
			value = int(raw_value)
		except:
			value = None
		return value

class RegexpVariable(Variable):
	"""Variable containing a regexp match.
	"""

	def load(self, raw_value):
		"""Converts an input regexp match into a string object.
		Returns: String, if the conversion succeeds;
		None, if the string is empty or the conversion fails.

		raw_value -- regexp match.
		"""
		if raw_value:
			try:
				value = str(raw_value).strip()
				if not value:
					value = None
			except:
				value = None
		else:
			value = None
		return value


class IpVariable(Variable):
	"""Variable containing an IP address.
	"""
		
	def equals(self, raw_value):
		"""Compares this IP address to a given one, OR
		Checks this IP address matchtype.
		Suported matchtypes: 'private', 'public'.
		
		raw_value -- Specific IP address, OR matchtype of IP.
		"""
		if self.value is None:
			output = False
		elif raw_value == 'private':
			output = (self.value.iptype() == 'PRIVATE')
		elif raw_value == 'public':
			output = (self.value.iptype() == 'PUBLIC')
		else:
			value = self.load(raw_value)
			output = (self.value == value)

		return output
		
	def load(self, raw_value):
		"""Converts an input raw value into a IP address.
		Returns: IP object, if the conversion succeeds;
		         None, if the conversion fails.

		raw_value -- The input raw value, representing a IP address
		             (eg. '192.168.1.1').
		"""
		try:
			ipaddr = IP(raw_value)
		except:
			ipaddr = None
		return ipaddr


class TimeVariable(Variable):
	"""Variable containing a timestamp value.
	"""
		
	def load(self, raw_value):
		"""Converts an input raw value into a timestamp.
		Returns: Datetime object, if the conversion succeeds;
		         None, if the conversion fails.

		raw_value -- The raw value, in string format (eg. '2014-12-20 15:01:02'),
		             or in milliseconds since Epoch  (eg. 1293581619000)
		"""
		if isinstance(raw_value, str):
			try:
				timestamp = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
			except:
				timestamp = None
		else:
			try:
				timestamp = datetime.utcfromtimestamp(float(raw_value)/1000)
			except:
				timestamp = None
		return timestamp


class TimedeltaVariable(TimeVariable):
	"""Variable containing a time duration.
	The value is a timedelta object.
	"""
	def __init__(self, start_value, end_value):
		"""Class constructor.

		start_value -- Raw start timestamp.
		end_value   -- Raw end timestamp.
		"""
		start_time = super(TimedeltaVariable, self).load(start_value)      # Python3: super().__init__()
		end_time   = super(TimedeltaVariable, self).load(end_value)        # Python3: super().__init__()
		try:
			self.value = end_time - start_time
		except TypeError:
			self.value = None
	
	def load(self, raw_value):
		"""Converts an input raw value into a timedelta.
		Returns: Timedelta object, if the conversion succeeds;
		         None, if the conversion fails.

		raw_value -- The time duration, in seconds (eg. 3600),
		"""
		try:
			duration = timedelta(seconds = int(raw_value))
		except:
			duration = None
		return duration

	def __repr__(self):
		"""Default string representation: number of seconds
		"""
		if self.value is not None:
			return str(self.value.total_seconds())
		else:
			return str(None)


class MultipleVariable(object):
	"""Multiple variable. Contains a list of variables.
	"""
	def __init__(self, variable):
		"""Class constructor.

		variable -- Single variable, first in the list.
		"""
		self.value = []
		self.value.append(variable)
		
	def equals(self, raw_value):
		"""Counts the amount of variables that equal the given value.
		Returns the number of matches.

		raw_value -- Single value to compare with.
		"""
		count = 0
		for f in self.value:
			if f.equals(raw_value):
				count += 1
		return count
	
	def belongs(self, start, end):
		"""Counts the amount of variables that belong to the given interval.
		Returns the number of matches.

		start -- Initial value of the interval (inclusive).
		end   -- Final value of the interval (exclusive).
                 'None' value means infinite.
		"""
		count = 0
		for f in self.value:
			if f.belongs(start, end):
				count += 1
		return count
		
	def __repr__(self):
		"""Class default string representation.
		"""
		return self.value.__str__()


#-----------------------------------------------------------------------
# Record Class
#-----------------------------------------------------------------------

class Record(object):
	"""Information record containing data variables. It is a dictonary of variables.
	
	The variables are defined in the user conf file, section VARIABLES.
	Each variable will be later used to define one or more features.
	
	A record looks like this:
	{flow_id: '4485422', src_ip: '192.168.1.2', src_port: 80, ...}
	
	Class Attributes:
		variables -- Dictionary of variables, indexed by their name.
		
	"""
	def __init__(self, line, variables, structured, all=False):
		self.variables = {}
		
		# For structured sources
		if structured:
			raw_values = line.split(',')
			#print(raw_values)

			for v in variables:
				try:
					vType = v['matchtype']
					vName = v['name']
					vWhere  = v['where']
				except KeyError as e:
					raise ConfigError(self, "VARIABLES: missing config key (%s)" %(e.message))	
				try:
					vMult = v['mult']
				except KeyError:
					vMult = False
				
				# Validate name
				if vName:
					vName = str(vName)
				else:
					raise ConfigError(self, "VARIABLE: empty id in variable")

				# Validate arg
				try:

					if isinstance(vWhere, list) and len(vWhere) == 2:
						if vWhere[0]>len(raw_values) or vWhere[1]>len(raw_values):
 							vValue = [None,	 None]
						else:
							vValue = [raw_values[vWhere[0]], raw_values[vWhere[1]]]
					else:
						if vWhere>len(raw_values):
 							vValue = None
						else:
							vValue = raw_values[vWhere]

				except (TypeError, IndexError) as e:
					raise ConfigError(self, "VARIABLES: illegal arg in \'%s\' (%s)" %(vName, e.message))

				except:
					vValue = None

				variable = list();
				# Validate matchtype
				if vType == 'string':
					variable.append(StringVariable(vValue))
				elif vType == 'number':
					variable.append(NumberVariable(vValue))
				elif vType == 'ip':
					variable.append(IpVariable(vValue))
				elif vType == 'time':
					variable.append(TimeVariable(vValue))
				elif vType == 'duration':
					if isinstance(vValue, list) and len(vValue) == 2:
						variable.append(TimedeltaVariable(vValue[0], vValue[1]))
					else:
						raise ConfigError(self, "VARIABLES: illegal arg in %s (two-item list expected)" %(vName))
				else:
					raise ConfigError(self, "VARIABLES: illegal matchtype in \'%s\' (%s)" %(vName, vType))
					
				# Add variable to the record
				if vMult:
					self.variables[vName] = MultipleVariable(variable)
				else:
					self.variables[vName] = variable

		# For unstructured sources

		else:

			for v in variables:
				try:
					vName = v['name']
					vWhere = v['where']
					vMatchType = v['matchtype']
					if isinstance(vWhere,str):
						vType = 'regexp'
						vComp = v['r_Comp']

				except KeyError as e:
					raise ConfigError(self, "VARIABLES: missing config key (%s)" %(e.message))


				# Validate matchtype
				if vType == 'regexp':

					try:
						if all:
							vValues = vComp.findall(line)
						else:
							vV = vComp.search(line)
							vValues = [vV.group(0)]

						variable = list();

						for vValue in vValues:

							if vMatchType == 'string':
								variable.append(StringVariable(vValue))

							elif vMatchType == 'number':
								variable.append(NumberVariable(vValue))

							elif vMatchType == 'ip':
								variable.append(IpVariable(vValue))

							elif vMatchType == 'time':
								variable.append(TimeVariable(vValue))

							elif vMatchType == 'duration':
								if isinstance(vValue, list) and len(vValue) == 2:
									variable.append(TimedeltaVariable(vValue[0], vValue[1]))
								else:
									raise ConfigError(self, "VARIABLES: illegal arg in %s (two-item list expected)" %(vName))


					except:
						variable = [None]
				else:
					raise ConfigError(self, "VARIABLES: illegal matchtype in '%s' (%s)" %(vName, vMatchType))


				self.variables[vName] = variable
	
	def __repr__(self):
		return "<%s - %d variables>" %(self.__class__.__name__, len(self.variables))
		
	def __str__(self):
		return self.variables.__str__()


#-----------------------------------------------------------------------
# Feature Class
#-----------------------------------------------------------------------

class Feature(object):
	"""Quantitative feature contained in an observation.
	
	This is an abstract class, and should not be directly instantiated. 
	Instead, use one of the subclasses, defined for each matchtype of feature:
	- SingleFeature    (matchtype 'single')
	- MultipleFeature  (matchtype 'multiple')
	- RangeFeature     (matchtype 'range')
	- RegExpFeature    (matchtype 'regexp')
	- DefaultFeature   (matchtype 'default')
	- ListFeature      (matchtype 'list')
	
	Class Attributes:
		value -- The value of the variable.
	"""
	def __init__(self, fconfig):
		"""Class constructor.

		raw_value -- Single value, as it is read from the input.
		"""
		self.fName  = fconfig['name']
		self.fVariable = fconfig['variable']
		self.fValue = fconfig['value']
		self.value = 0

	def add(self, var):
		"""Adds a variable to the feature if it is suitable.
		"""
		self.value += var.equals(self.fValue)

	def aggregate(self, feature):
		"""Adds a feature to the feature.
		"""
		if not isinstance(feature, Feature):
			raise AggregateError (self, "Ubale to add %s and %s" %(self.__class__.__name__, feature.__class__.__name__))

		if feature.value is not None:
			self.value += feature.value
		

	def __repr__(self):
		"""Class default string representation.
		"""
		return self.value.__str__()


class SingleFeature(Feature):
	"""Counter of a single value (e.g port 80).
	"""

	def __init__(self, fconfig):

		if isinstance(fconfig['value'], list):
			raise ConfigError(self, "FEATURES: illegal value in '%s' (single item expected)" %(fconfig['value']))

		super(SingleFeature, self).__init__(fconfig)



class MultipleFeature(Feature):
	"""Counter of several values (e.g ports 80 & 8080).
	"""

	def __init__(self, fconfig):

		if not isinstance(fconfig['value'], list):
			raise ConfigError(self, "FEATURES: illegal value in '%s' (list of items expected)" %(fconfig['value']))

		super(MultipleFeature, self).__init__(fconfig)

	def add(self, var):

		for v in self.fValue:
			super(MultipleFeature, self).add(var)


class RangeFeature(Feature):
	"""Counter of several values (e.g ports 80 & 8080).
	"""

	def __init__(self, fconfig):

		if isinstance(fconfig['value'], list) and len(fconfig['value']) == 2:

			super(RangeFeature, self).__init__(fconfig)

			self.start = self.fValue[0]
			self.end =  self.fValue[1]
			if str(self.end).lower() == 'inf':
				self.end  = None
		else:
			raise ConfigError(self, "FEATURES: illegal value in '%s' (two-item list expected)" %(fconfig['value']))


	def add(self, var):
		self.value += var.belongs(self.start, self.end)



class RegExpFeature(Feature):
	"""Counter of reg. expresions, for unstructured data
	"""

	def __init__(self, fconfig):
		if isinstance(fconfig['value'], list):
			raise ConfigError(self, "FEATURES: illegal value in '%s' (single item expected)" %(fconfig['name']))

		super(RegExpFeature, self).__init__(fconfig)

		self.r_Comp = fconfig['r_Comp']


	def add(self, var):

		try:
			matchObj = self.r_Comp.match(str(var).replace('[','').replace(']',''))
		except re.error as e:
			raise ConfigError(self, "FEATURES: illegal regexp in '%s' (%s)" %(self.fName, e.message))
		
		if matchObj:
			self.value += 1


		
class DefaultFeature(Feature):
	"""Counter of number of variable instances not identified in other features
	"""
				
	def add(self, record, data):

		counter = 0
		for i in range(len(data)):
			if data[i].fVariable == self.fVariable:
				counter += data[i].value

		self.value += len(record.variables[self.fVariable]) - counter

class TotalFeature(Feature):
	"""Counter of number of variable instances 
	"""
				
	def add(self, var):

		self.value += 1

#-----------------------------------------------------------------------
# Observation Class
#-----------------------------------------------------------------------

class Observation(object):
	"""Observation array containing data suitable for the analysis.
	
	An observation array represents one row of data, and consist of a
	number of instances of the defined features. A feature represents
	one column of data. Thus, the input of the multivariate analysis
	engine consist of a N-by-M data matrix (N observations, M features).
	
	The features are defined in the user conf file, section features.
	Each feature is a integer counter defined from a specific variable.
	
	An observation looks like this:
	[0, 1, 0, 0, 2, 0, 0, 0, 3, 1, 0, ...]

	Class Attributes:
		data  -- Array of data values.

	"""


	def __init__(self, data, debug=None):

		self.data = data

    	
	@classmethod
	def fromRecord(cls, record, FEATURES):
		"""Creates an observation from a record of variables.
		record    -- Record object.
		FEATURES -- List of features configurations."""

		data  = [None] * len(FEATURES)    # Data array (counters)
		defaults = []		               # tracks default features

		for i in range(len(FEATURES)):
			try:
				fType  = FEATURES[i]['matchtype']

				# Validate matchtype
				if fType == 'single':
					feature = SingleFeature(FEATURES[i])
				elif fType == 'multiple':
					feature = MultipleFeature(FEATURES[i])
				elif fType == 'range':
					feature = RangeFeature(FEATURES[i])
				elif fType == 'regexp':
					feature = RegExpFeature(FEATURES[i])
				elif fType == 'default':
					feature = DefaultFeature(FEATURES[i])
				elif fType == 'total':
					feature = TotalFeature(FEATURES[i])
				else:
					raise ConfigError(cls, "FEATURES: illegal matchtype in \'%s\' (%s)" %(FEATURES[i]['name'], fType))


			except KeyError as e:
				raise ConfigError(cls, "FEATURES: missing config key (%s)" %(e.message))


			# Calculate feature 

			# Iterate through all the features in the conf file. For each iteration, check the matchtype of the variable 
			# involved. Then, check the value of the variable asociated to the feature. If there is a match, the counters
			# of the observations are increased. --> FaaC (Feature as a counter)

			variable = record.variables[FEATURES[i]['variable']]		

			data[i]  = feature
			
			for var in variable:
				if var is not None:
					if fType == 'default':
						if i not in defaults:
							defaults.append(i)
					
					else:
						data[i].add(var)
							
		# Manage default variables
		for d in defaults:
			data[d].add(record,data)	

		return cls(data)		

			
	def aggregate(self, obs):
		""" Aggregates this observation with a new one.
			obs -- Observation object to merge with.
		"""
		
		try:
			for i in range(len(self.data)):
				self.data[i].aggregate(obs.data[i])
		except IndexError as e:
			raise AggregateError (self, "Unable to aggregate data arrays (%s)" %(e.message))


	def fuse(self, data):
		""" Aggregates this observation with a new one.
			obs -- Observation object to merge with.

		"""
		self.data += data


	def zeroPadding(self, N):

		self.data = [0] * N + self.data


	def __repr__(self):
		return "<%s - %d vars>" %(self.__class__.__name__, len(self.data))
		
	def __str__(self):
		return self.data.__str__()


#-----------------------------------------------------------------------
# Exception and Error Classes
#-----------------------------------------------------------------------

class ConfigError(Exception):
	def __init__(self, obj, message=''):
		self.obj = obj
		self.message = message
		self.msg = "ERROR - Config File - %s" %(message)

	def __str__(self):
	        return repr(self.msg)

class AggregateError(Exception):
	def __init__(self, obj, message=''):
		self.obj = obj
		self.message = message
		self.msg = "ERROR - Aggregate - %s" %(message)

	def __str__(self):
	        return repr(self.msg)


#-----------------------------------------------------------------------
# Read configuration file
#-----------------------------------------------------------------------

def getConfiguration(config_file):
	'''
	Function to load config file
	'''
	stream = open(config_file, 'r')
	conf = yaml.load(stream)
	if 'FEATURES' not in conf:
		conf['FEATURES'] = {}

	stream.close()
	return conf


def loadConfig(output, dataSources, parserConfig):
	'''
	Function to load configuration from the config files
	'''
	config = {}
	# Output settings 

	try:
		config['OUTDIR'] = output['dir']
		if not config['OUTDIR'].endswith('/'):
			config['OUTDIR'] = config['OUTDIR'] + '/'
	except (KeyError, TypeError):
		config['OUTDIR'] = 'OUTPUT/'
		print(" ** Default output directory: '%s'" %(config['OUTDIR']))

	try:
		shutil.rmtree(config['OUTDIR']+'/')
	except:
		pass

	if not os.path.exists(config['OUTDIR']):
		os.mkdir(config['OUTDIR'])
		print("** creating directory %s" %(config['OUTDIR']))

	try:
		config['OUTSTATS'] = output['stats']
	except (KeyError, TypeError):
		config['OUTSTATS'] = 'stats.log'
		print(" ** Default log file: '%s'" %(config['OUTSTATS']))
	try:
		config['OUTW'] = output['weights']
	except (KeyError, TypeError):
		# print " ** Default weights file: '%s'" %(config['OUTW'])
		config['OUTW'] = 'weights.dat'

	try: 
		config['Time'] = parserConfig['SPLIT']['Time']

	except:
		config['Time'] = 0	

	try: 
		config['Cores'] = int(parserConfig['Processes'])

	except:
		print("**ERROR** Config file missing field: Processes")
		exit(1)

	try: 
		config['Keys'] = parserConfig['Keys']

	except:
		config['Keys'] = []

	try: 
		config['Csize'] = 1024 * 1024 * int(parserConfig['Max_chunk'])

	except:
		config['Csize'] = 1024 * 1024 * config['Cores'];

	if 'Lperc' in parserConfig:
		config['Lperc'] = float(parserConfig['Lperc'])
	else:
		config['Lperc'] = 0.01;

	if 'EndLperc' in parserConfig:
		config['EndLperc'] = float(parserConfig['EndLperc'])
	else:
		config['EndLperc'] = 0.0001;

	if 'All' in parserConfig:
		config['All'] = bool(parserConfig['All'])
	else:
		config['All'] = False;
		

	# Sources settgins
	config['SOURCES'] = {}
	for source in dataSources:
		config['SOURCES'][source] = {}
		config['SOURCES'][source]['CONFILE'] = dataSources[source]['config']
		config['SOURCES'][source]['CONFIG'] = getConfiguration(dataSources[source]['config'])
		config['SOURCES'][source]['FILESTRAIN'] = glob.glob(dataSources[source]['learning'])
		config['SOURCES'][source]['FILES'] = glob.glob(dataSources[source]['parsing'])
		config['SOURCES'][source]['FILESDEP'] = glob.glob(dataSources[source]['deparsing'])

	config ['FEATURES'] = {}
	config['STRUCTURED'] = {}
	config['SEPARATOR'] = {}

	for source in config['SOURCES']:
		config['FEATURES'][source] = config['SOURCES'][source]['CONFIG']['FEATURES']
		config['STRUCTURED'][source] = config['SOURCES'][source]['CONFIG']['structured']
		
		for i in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
			# Validate name
			if config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['name']:
				config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['name'] = str(config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['name'])
			else:
				raise ConfigError(self, "VARIABLE: empty id in variable")

		for i in range(len(config['SOURCES'][source]['CONFIG']['FEATURES'])):
			# Validate name
			if config['SOURCES'][source]['CONFIG']['FEATURES'][i]['name']:
				config['SOURCES'][source]['CONFIG']['FEATURES'][i]['name'] = str(config['SOURCES'][source]['CONFIG']['FEATURES'][i]['name'])
			else:
				raise ConfigError(self, "FEATURES: missing variable name")

			# Validate variable
			try:				
				config['SOURCES'][source]['CONFIG']['FEATURES'][i]['variable']
			except KeyError as e:
				config['SOURCES'][source]['CONFIG']['FEATURES'][i]['variable'] = None

		if not config['STRUCTURED'][source]:
			config['SEPARATOR'][source] = config['SOURCES'][source]['CONFIG']['separator']	

			for i in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
				config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['r_Comp'] = re.compile(config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['where'])

			for i in range(len(config['SOURCES'][source]['CONFIG']['FEATURES'])):
					if config['SOURCES'][source]['CONFIG']['FEATURES'][i]['matchtype'] == 'regexp':
						config['SOURCES'][source]['CONFIG']['FEATURES'][i]['r_Comp'] = re.compile(config['SOURCES'][source]['CONFIG']['FEATURES'][i]['value']+'$')

		else:
			config['SEPARATOR'][source] = "\n"

			for i in range(len(config['SOURCES'][source]['CONFIG']['FEATURES'])):
					if config['SOURCES'][source]['CONFIG']['FEATURES'][i]['matchtype'] == 'regexp':
						config['SOURCES'][source]['CONFIG']['FEATURES'][i]['r_Comp'] = re.compile(config['SOURCES'][source]['CONFIG']['FEATURES'][i]['value'])
	
	
	
		# Preprocessing nfcapd files to obtain csv files.
		for source in dataSources:
			out_files = []
			for file in config['SOURCES'][source]['FILES']:
				if 'nfcapd' in file:
	
					out_file = '/'.join(file.split('/')[:-1]) + '/temp_' + file.split('.')[-1] + ""
					os.system("nfdump -r " + file + " -o csv >>"+out_file)
					os.system('tail -n +2 '+out_file + '>>' + out_file.replace('temp',source))
					os.system('head -n -3 ' + out_file.replace('temp',source) + ' >> ' + out_file.replace('temp',source) + '.csv')
					out_files.append(out_file.replace('temp',source) + '.csv')
					os.remove(out_file)
					os.remove(out_file.replace('temp',source))
					config['SOURCES'][source]['FILES'] = out_files
					delete_nfcsv = out_files
	
		# Process weight and made a list of features
		config['features'] = []
		config['weights'] = []
	
		for source in config['FEATURES']:
			# Create weight file
	
			for feat in config['SOURCES'][source]['CONFIG']['FEATURES']:
				try:	
					config['features'].append(feat['name'])
				except:
					print("FEATURES: missing config key (%s)" %(e.message))
					exit(1)	

				try:	
					fw = feat['weight']
					for var in config['SOURCES'][source]['CONFIG']['VARIABLES']:
						if var['name'] == feat['variable']:
							try:
								fw2 = var['weight']
							except:
								fw2 = 1

							fw = fw*fw2
				except:
					fw = 1

				config['weights'].append(str(fw))



	return config

