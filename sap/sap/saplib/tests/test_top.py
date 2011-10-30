import unittest
from gen import Gen
import os
import sys
from inspect import isclass
import json
import saputils

class Test (unittest.TestCase):
	"""Unit test for the gen_top.v"""

	def setUp(self):

		self.gen = None
		self.gen_module = __import__("gen_top")
		self.dbg = False
		if "SAPLIB_DEBUG" in os.environ:
			if (os.environ["SAPLIB_DEBUG"] == "True"):
				self.dbg = True

		print "debug flag: " + str(self.dbg)

		os.environ["SAPLIB_BASE"] = sys.path[0] + "/saplib"
		for name in dir(self.gen_module):
			obj = getattr(self.gen_module, name)
			if isclass(obj) and issubclass(obj, Gen) and obj is not Gen:
				self.gen = obj()
				print "found " + name

		return

	def test_gen_top_mem(self):
		"""generate a top.v file with memory bus"""
		tags = {}
		top_buffer = ""
		#get the example project data
		try:
			filename = os.getenv("SAPLIB_BASE") + "/example_project/mem_example.json"
			filein = open(filename)
			filestr = filein.read()
			tags = json.loads(filestr)

		except IOError as err:
			print "File Error: " + str(err)
			self.assertEqual(False, True)

		try:
			filename = os.getenv("SAPLIB_BASE") + "/hdl/rtl/wishbone/wishbone_top.v"
			filein = open(filename)
			top_buffer = filein.read()
			filein.close()
		except IOError as err:
			print "File Error: " + str(err)
			self.assertEqual(False, True)

		#print "buf: " + top_buffer

		result = self.gen.gen_script(tags, buf = top_buffer, debug=self.dbg)
		if (self.dbg):
			print "Top file: \n" + result

		self.assertEqual(len(result) > 0, True)


	def test_is_not_wishbone_port(self):
		result = False
		result = self.gen.is_wishbone_port("gpio")	
		self.assertEqual(result, False)

	def test_is_wishbone_port(self):
		result = False	
		result = self.gen.is_wishbone_port("lcd_stb_i")
		self.assertEqual(result, True)

	def test_gen_top(self):
		"""generate a top.v file"""
		
		tags = {}
		top_buffer = ""
		#get the example project data
		try:
			filename = os.getenv("SAPLIB_BASE") + "/example_project/gpio_v2.json"
			filein = open(filename)
			filestr = filein.read()
			tags = json.loads(filestr)

		except IOError as err:
			print "File Error: " + str(err)
			self.assertEqual(False, True)

		try:
			filename = os.getenv("SAPLIB_BASE") + "/hdl/rtl/wishbone/wishbone_top.v"
			filein = open(filename)
			top_buffer = filein.read()
			filein.close()
		except IOError as err:
			print "File Error: " + str(err)
			self.assertEqual(False, True)

		#print "buf: " + top_buffer

		result = self.gen.gen_script(tags, buf = top_buffer, debug=self.dbg)
		if (self.dbg):
			print "Top file: \n" + result

		self.assertEqual(len(result) > 0, True)


	def test_generate_buffer_slave(self):
		
		absfilepath = saputils.find_rtl_file_location("simple_gpio.v")
		#print "simple_gpio.v location: " + absfilepath
		slave_keywords = [
			"DRT_ID",
			"DRT_FLAGS",
			"DRT_SIZE"
		]
		tags = saputils.get_module_tags(filename = absfilepath, bus="wishbone", keywords = slave_keywords) 

			

		self.gen.wires = [
			"clk",
			"rst"
		]
		result = self.gen.generate_buffer(name="wbs", index=0, module_tags = tags) 

		buf = result
		#print "out:\n" + buf
		self.assertEqual(len(buf) > 0, True)

#	def test_generate_buffer_slave_hard(self):
#		absfilepath = saputils.find_rtl_file_location("wb_ddr.v")
#		#print "simple_gpio.v location: " + absfilepath
#		slave_keywords = [
#			"DRT_ID",
#			"DRT_FLAGS",
#			"DRT_SIZE"
#		]
#		tags = saputils.get_module_tags(filename = absfilepath, bus="wishbone", keywords = slave_keywords) 
#
#		print tags
#
#		self.gen.wires = [
#			"clk",
#			"rst"
#		]
#		result = self.gen.generate_buffer(name="wbs", index=0, module_tags = tags) 
#
#		buf = result
#		#print "out:\n" + buf
#		self.assertEqual(len(buf) > 0, True)




	def test_generate_buffer_io_handler(self):

		absfilepath = saputils.find_rtl_file_location("uart_io_handler.v")
		#print "uart_io_handler.v location: " + absfilepath

		tags = saputils.get_module_tags(filename = absfilepath, bus="wishbone") 
		self.gen.wires=[
			"clk",
			"rst"
		]

		result = self.gen.generate_buffer(name = "uio", module_tags = tags) 
		
		buf = result
		#print "out:\n" + buf
		self.assertEqual(len(buf) > 0, True)

if __name__ == "__main__":
	unittest.main()
