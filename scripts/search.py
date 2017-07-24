#!/usr/bin/env python

import argparse

def main():
	args = get_arguments()

	src_col = int(args.colsrc)
	inp_col = int(args.colinp)
	if args.max:
		max_values = int(args.max)
	else:
		max_values = None
	
	# Read source values before search.
	stream = open(args.source, 'r')
	line = stream.readline()
	sourceValues = []
	count = 0
	while line:
		fieldList = line.split(',')
		value = fieldList[src_col]
		sourceValues.append(value)
		count += 1
		if max_values:
			if count >= max_values:
				break
		line = stream.readline()
	stream.close()
	print "Loaded %d source values." %(len(sourceValues))

	# Search values in the input files.
	for inpath in args.files:
		matches = 0
		print "Searching in file: %s" %(inpath)
		stream = open(inpath, 'r')
		line = stream.readline()
		while line:
			fieldList = line.split(',')
			value = fieldList[inp_col]
			for v in sourceValues:
				if value == v:
					matches += 1
					#print "Match: %s" %(v)
					break
			line = stream.readline()
		print "Total matches: %d / %d" %(matches, len(sourceValues))
		print

		

def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Search fields in datasources.''')
	parser.add_argument('-o','--output', metavar='OUTPUT', default='discover_result.dat', help='Output file. Default: "discover_result.dat".')

	parser.add_argument('-cs','--colsrc', metavar='COLUMN_SRC', default=0, help='Column (order) of the searching field. Default: 0')
	parser.add_argument('-ci','--colinp', metavar='COLUMN_INP', default=0, help='Column (order) of the field to search in. Default: 0')
	parser.add_argument('-m','--max', metavar='MAX', help='Maximum number of source values to search.')

	parser.add_argument('-s','--source', metavar='SOURCE', help='Source file that containing the fields you want to search.')
	parser.add_argument('files', metavar='FILE', nargs='+',help='Input data files (CSV format) to search in.')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

