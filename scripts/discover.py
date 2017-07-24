#!/usr/bin/env python

import argparse
from datetime import datetime
from collections import Counter

def main():
	args = get_arguments()
	col = int(args.col)

	print "<< <input_file_name> (<new_values> / <total_values>)"
	print "----------------------------------------------------"


	uniqueValues = Counter([])
	fileCount = 0
	for inpath in args.files:
		stream = open(inpath, 'r')
		fileCount += 1
		line = stream.readline()
		while line:
			if line.strip():
				fieldList = line.split(',')
				value = fieldList[col].strip()
				if args.delseconds:
					value = delete_seconds(value)
				if args.verbose:
					if value not in uniqueValues:
						print "New: %s" %(value)
				uniqueValues[value] += 1
			line = stream.readline()

		stream.close()
		print "#%s / %s << %s (%d values)" %(fileCount, len(args.files), inpath, len(uniqueValues))
				
	outstream = open(args.output, 'w')
	li = uniqueValues.most_common(len(uniqueValues))
	for v in li:
		outstream.write(str(v[0]) + ', ' + str(v[1]) + '\n')
	outstream.close()
	print "----------------------------------------------------"
	print "%d input files" %(fileCount)
	print "%d unique values" %(len(uniqueValues))
	print "Written >> %s" %(args.output)
	
	
def delete_seconds(date_str):
	"""Delete miliseconds and seconds from the date string"""
	parts = date_str.split('.')
	dt = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
	return datetime.strftime(dt, "%Y-%m-%d %H:%M")



def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Discover the set of possible values of a given field.''')
	parser.add_argument('-o','--output', metavar='OUTPUT', default='discover_result.dat', help='Output file. Default: "discover_result.dat".')
	parser.add_argument('-c','--col', metavar='COLUMN', default=0, help='Column (order) of the field to discover. Default: 0')

	parser.add_argument('-d','--delseconds', action='store_true', help='Remove seconds and miliseconds from the date string (use only when discovering date strings)')
	parser.add_argument('-v','--verbose', action='store_true', help='Show verbose information (discovered values)')

	parser.add_argument('files', metavar='FILE', nargs='+',help='Input data files (CSV format)')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

