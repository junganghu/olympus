#!/usr/bin/env python
import json
import sapfile
import saputils
import sap_graph_manager
from sap_graph_manager import Slave_Type
from sap_graph_manager import Node_Type
from sap_graph_manager import get_unique_name

def enum(*sequential, **named):
	enums = dict(zip(sequential, range(len(sequential))), **named)
	return type('Enum', (), enums)


class SapGraphController:
	def __init__(self):
		self.new_design()
		return


	def load_config_file(self, file_name, debug=False):
		"""
		Loads a sycamore configuration file into memory
		"""
		json_string = ""
		try:
			#open up the specified JSON project config file
			filein = open (file_name)
			#copy it into a buffer
			json_string = filein.read()
			filein.close()
		except IOError as err:
			print("File Error: " + str(err))
			return False

		self.project_tags = json.loads(json_string)
		return True

	def initialize_graph(self):
		"""
		Initializes the graph and project tags
		"""

		#clear any previous data
		self.sgm.clear_graph()


		#set the bus type
		if self.project_tags["TEMPLATE"] == "wishbone_template.json":
			self.set_bus_type("wishbone")
		elif self.project_tags["TEMPLATE"] == "axie_template.json":
			self.set_bus_type("axie")

		#add the nodes that are always present
		self.sgm.add_node(	"Host Interface", 
							Node_Type.host_interface)
		self.sgm.add_node(	"Master", 
							Node_Type.master)
		self.sgm.add_node(	"Memory", 
							Node_Type.memory_interconnect)
		self.sgm.add_node(	"Peripherals", 
							Node_Type.peripheral_interconnect)
		self.sgm.add_node(	"DRT",
							Node_Type.slave,
							Slave_Type.peripheral,
							slave_index = 0)

		#get all the unique names for accessing nodes
		hi_name = get_unique_name(	"Host Interface", 
									Node_Type.host_interface) 
		m_name = get_unique_name(	"Master",
									Node_Type.master)
		mi_name = get_unique_name(	"Memory",
									Node_Type.memory_interconnect)
		pi_name = get_unique_name(	"Peripherals",
									Node_Type.peripheral_interconnect)
		drt_name = get_unique_name(	"DRT",
									Node_Type.slave,
									Slave_Type.peripheral,
									slave_index = 0)

		#attach all the appropriate nodes
		self.sgm.connect_nodes(hi_name, m_name)
		self.sgm.connect_nodes(m_name, mi_name)
		self.sgm.connect_nodes(m_name, pi_name)
		self.sgm.connect_nodes(pi_name, drt_name)

		#attempt to load data from the tags
		sp_count = self.sgm.get_number_of_peripheral_slaves()
		if "SLAVES" in self.project_tags:
			for slave_name in self.project_tags["SLAVES"].keys():
				self.sgm.add_node(	slave_name,
									Node_Type.slave,
									Slave_Type.peripheral,
									slave_index = sp_count)
				sp_count += 1

		#load all the memory slaves
		sm_count = self.sgm.get_number_of_memory_slaves()
		if "MEMORY" in self.project_tags:
			for slave_name in self.project_tags["MEMORY"].keys():
				self.sgm.add_node(	slave_name,
									Node_Type.slave,
									Slave_Type.memory,
									slave_index = sm_count)

		#check if there is a host insterface defined
		if "INTERFACE" in self.project_tags:
			file_name = saputils.find_rtl_file_location(self.project_tags["INTERFACE"]["filename"])
			parameters = saputils.get_module_tags(	filename = file_name, bus=self.get_bus_type())
			self.sgm.set_parameters(hi_name, parameters)
		
		return True

	def get_number_of_memory_slaves(self):
		return self.sgm.get_number_of_memory_slaves()

	def get_number_of_peripheral_slaves(self):
		return self.sgm.get_number_of_peripheral_slaves()

	def save_config_file(self, file_name):
		"""
		Saves a module stored in memory to a file
		"""

		#if there are no slaves on the memory interconnect
		#then don't generate the structure in the JSON file for it
		return

	def set_project_location(self, location):
		"""
		sets the location of the project to output
		"""
		self.project_tags["BASE_DIR"] = location
	
	def get_project_location(self):
		return self.project_tags["BASE_DIR"]
		

	def set_project_name(self, name):
		"""
		sets the name of the output project
		"""
		self.project_tags["PROJECT_NAME"] = name

	def get_project_name(self):
		return self.project_tags["PROJECT_NAME"]

	def set_vendor_tools(self, vendor_tool):
		"""
		sets the vendor build tool, currently only
		Xilinx is supported
		"""
		self.project_tags["BUILD_TOOL"] = vendor_tool

	def get_vendor_tools(self):
		return self.project_tags["BUILD_TOOL"]

	def set_board_name(self, board_name):
		"""
		sets the name of the board to use
		"""
		if "CONSTRAINTS" not in self.project_tags.keys():
			self.project_tags["CONSTRAINTS"] = {}

		if "board" not in self.project_tags["CONSTRAINTS"].keys():
			self.project_tags["CONSTRAINTS"]["board"] = ""
				
		self.project_tags["CONSTRAINTS"]["board"] = board_name
	
	def get_board_name(self):
		if "CONSTRAINTS" in self.project_tags.keys():
			if "board" in self.project_tags["CONSTRAINTS"].keys():
				return self.project_tags["CONSTRAINTS"]["board"]

		return "undefined"
	
	def set_constraint_file_name(self, constraint_file_name):
		"""
		sets the constraint file name
		"""
		if "CONSTRAINTS" not in self.project_tags.keys():
			self.project_tags["CONSTRAINTS"] = {}

		if "constraint_files" not in self.project_tags["CONSTRAINTS"].keys()
			self.project_tags["CONSTRAINTS"]["constraint_files"] = []

		self.project_tags["CONSTRAINTS"]["constraints_files"] = [constraint_file_name]

	def append_constraint_file_name(self, constraint_file_name):
		if "CONSTRAINTS" not in self.project_tags.keys():
			self.project_tags["CONSTRAINTS"] = {}

		if "constraint_files" not in self.project_tags["CONSTRAINTS"].keys()
			self.project_tags["CONSTRAINTS"]["constraint_files"] = []

		self.project_tags["CONSTRAINTS"]["constraints_files"].append(constraint_file_name)
	
	def get_constraint_file_names(self):
		if "CONSTRAINTS" in self.project_tags.keys():
			if "constraint_file_name" in self.project_tags["CONSTRAINTS"].keys():
				return self.project_tags["CONSTRAINTS"]["constraint_file_name"]


		return []
	
	def set_fpga_part_number(self, fpga_part_number):
		"""
		sets the part number, this is used when generating
		the project
		"""
		if "CONSTRAINTS" not in self.project_tags.keys():
			self.project_tags["CONSTRAINTS"] = {}

		if "device" not in self.project_tags["CONSTRAINTS"].keys()
			self.project_tags["CONSTRAINTS"]["device"] = ""

		self.project_tags["CONSTRAINTS"]["device"] = fpga_part_number

	def get_fpga_part_number(self):
		if "CONSTRAINTS" in self.project_tags.keys():
			if "device" in self.project_tags["CONSTRAINTS"].keys():
				return self.project_tags["CONSTRAINTS"]["device"]

		return "undefined"
	

	def new_design(self):
		"""
		Initialize an empty design
		"""
		self.sgm = sap_graph_manager.SapGraphManager()
		self.bus_type = "wishbone"
		self.tags = {}
		self.file_name = ""
		self.project_tags = {}
		self.project_tags["PROJECT_NAME"] = "project"
		self.project_tags["BASE_DIR"] = "~/sycamore_projects"
		self.project_tags["BUILD_TOOL"] = "xilinx"
		self.project_tags["TEMPLATE"] = "wishbone_template.json"
		self.project_tags["INTERFACE"] = {}
		self.project_tags["INTERFACE"]["filename"] = "uart_io_handler.v"
		self.project_tags["SLAVES"] = {}
		self.project_tags["MEMORY"] = {}
		self.project_tags["CONSTRAINTS"] = {}
		self.project_tags["CONSTRAINTS"]["constraint_files"] = []
		self.project_tags["CONSTRAINTS"]["board"] = ""
		self.project_tags["CONSTRAINTS"]["device"] = ""
		self.project_tags["CONSTRAINTS"]["bind"] = {}


		return

	def generate_project(self):
		"""
		Generates the output project that can be used
		to create a bit image
		"""
		return

	def set_bus_type(self, bus_type):
		"""
		Set the bus type to Wishbone or Axie
		"""
		self.bus_type = bus_type
		return

	def get_bus_type(self):
		return self.bus_type

	def set_host_interface(self, host_interface_name, debug = False):
		"""
		sets the host interface type
		"""
		hi_name = get_unique_name(	"Host Interface", 
									Node_Type.host_interface) 

		node_names = self.sgm.get_node_names()
		if hi_name not in node_names:
			self.sgm.add_node(	"Host Interface", 
								Node_Type.host_interface)

		#check if the host interface is valid
		file_name = ""
		try:
			file_name = saputils.find_module_filename(host_interface_name)
		except ModuleNotFound as ex:
			if debug:
				print "Invalid Module Name"

#XXX: Need to inform the user that the Host Interface Selected was
#not valid
				return False

		#if the host interface is valid then get all the tags
		parameters = saputils.get_module_tags(	filename = file_name, bus=self.get_bus_type())
		#and set them up
		self.sgm.set_parameters(hi_name, parameters)
		return True

	def get_host_interface(self):
		return

	def add_arbitrator(self, 	host_name, 
								host_type, 
								host_index, 
								slave_name, 
								slave_type, 
								slave_index):
		"""
		adds an arbitrator and attaches it between the host and
		the slave
		"""

	def remove_arbitrator(self,	host_name,
								host_type,
								host_index):
		"""
		Finds and removes the arbitrator from the host
		"""

	def add_slave(self, slave_name, slave_type, slave_index):
		"""
		Adds a slave to the specified bus at the specified index
		"""
		#check if the slave_index makes sense
		#if slave index s -1 then add it to the next available location
		return

	def remove_slave(self, slave_name = None, slave_type = Slave_Type.peripheral, slave_index=0):
		"""
		Removes slave from specified index
		"""
		#can't remove the DRT so if the index is 0 then don't try

		#it's possible to remove the node given only the
		#Slave_Type, and the slave_index

		#check if the slave_name is 'None', if so then
		#we need to search for the slave_name
		return

	def move_slave(self, 	slave_name = None, 
							from_slave_type = Slave_Type.peripheral, 
							from_slave_index = 0,
							to_slave_type = Slave_Type.peripheral,
							to_slave_index = 0):
		"""
		move slave from one place to another,
		the slave can be moved from one bus to another
		and the index position can be moved
		"""
		return

	
	


