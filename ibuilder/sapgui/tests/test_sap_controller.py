import unittest
import os
import sys
import json
import mock

# Append to path so imports work.
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'saplib'))

import sapfile
import saputils
import sap_controller as sc
from gen_scripts.gen import Gen
from sap_graph_manager import SlaveType, NodeType, SlaveError
from sap_controller import StateError

class UTest(unittest.TestCase):
  '''Unit tests for sap_controller.py'''

  # Data found in saplib/example_project/gpio_example.json
  EXAMPLE_CONFIG = {
    "BASE_DIR": "~/projects/sycamore_projects",
    "board": "xilinx-s3esk",
    "PROJECT_NAME": "example_project",
    "TEMPLATE": "wishbone_template.json",
    "INTERFACE": {
      "filename": "uart_io_handler.v",
      "bind": {
        "phy_uart_in": {
          "port": "RX",
          "direction": "input"
        },
        "phy_uart_out": {
          "port": "TX",
          "direction": "output"
        }
      }
    },
    "SLAVES": {
      "gpio1": {
        "filename":"wb_gpio.v",
        "bind": {
          "gpio_out[7:0]": {
            "port":"led[7:0]",
            "direction":"output"
          },
          "gpio_in[3:0]": {
            "port":"switch[3:0]",
            "direction":"input"
          }
        }
      }
    },
    "bind": {},
    "constraint_files": []
  }

  # New config from SapController.
  NEW_CONFIG = {
    "PROJECT_NAME": "project",
    "BASE_DIR": "~/sycamore_projects",
    "BUILD_TOOL": "xilinx",
    "TEMPLATE": "wishbone_template.json",
    "INTERFACE": {
      "filename": "uart_io_handler.v"
    },
    "SLAVES": {},
    "MEMORY": {},
    "board": "sycamore1",
    "bind": {},
    "constraint_files": []
  }

  # Data found in saplib/hdl/boards/xilinx-s3esk/config.json
  BOARD_CONFIG = {
    "board_name": "Spartan 3 Starter Board",
    "vendor": "Digilent",
    "fpga_part_number": "xc3s500efg320",
    "build_tool": "xilinx",
    "default_constraint_files": [
      "s3esk_sycamore.ucf"
    ],
    "invert_reset": False
  }

  # Files found in /saplib/hdl/boards/xilinx-s3esk/ ending in 'ucf'
  BOARD_CONSTRAINT_FILES = [
    's3esk_ddr.ucf',
    's3esk_sycamore.ucf',
    's3esk_tft.ucf',
    'sycamore_serial.ucf'
  ]

  def setUp(self):
    '''Creates a new SapController for each test.'''
    self.sc = sc.SapController()

  def test_load_config_file(self):
    '''Loads the config file and compares it to EXAMPLE_CONFIG.'''
    # Set up the object so that we test only this function.
    self.sc.get_board_config = mock.Mock(return_value=self.BOARD_CONFIG)
    self.sc.get_project_constraint_files = mock.Mock(
        return_value=self.BOARD_CONFIG['default_constraint_files'])

    # Load the example file from the example dir.
    fname = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
        "saplib", "example_project", "gpio_example.json")
    self.assertTrue(self.sc.load_config_file(fname),
        'Could not get file "%s".  Please ensure that it exists\n' +
        '(re-checkout from the git repos if necessary)')

    # Check that the state of the controller is as it should be.
    self.assertEqual(self.sc.project_tags, self.EXAMPLE_CONFIG)
    self.assertEqual(self.sc.filename, fname)
    self.assertEqual(self.sc.build_tool, {})
    self.assertEqual(self.sc.board_dict, self.BOARD_CONFIG)

  def test_load_config_file_raises_typeerror_on_none(self):
    '''Tests that load_config_file raises an TypeError when passed None.'''
    self.assertRaises(TypeError, self.sc.load_config_file, None)

  def test_load_config_file_raises_ioerror_on_dne(self):
    '''Tests that load_config_file raises an IOError when the file does not
    exist.'''
    self.assertRaises(IOError, self.sc.load_config_file,
        os.path.join('foo', 'bar', 'baz'))

  def test_get_master_bind_dict(self):
    '''Tests get_master_bind_dict against a bunch of fake data.'''

    # Fake loading the config file.
    self.sc.project_tags = self.EXAMPLE_CONFIG

    # Some mock objects to create mock methods with.
    hi = mock.Mock()
    hi.unique_name = "uniquename0"
    hi.binding = {'0': 'u0', '1': 'u1'}

    slaves = []
    for i in xrange(4):
      slaves.append(mock.Mock())
      slaves[i].unique_name = 'slavename%d' % i
      slaves[i].binding = { 's%d' % (2*i+2): 'even', 's%d' % (2*i+3): 'odd' }

    # The mock methods that use the above mock objects.
    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_node_bindings = (lambda x:
        (x == hi.unique_name and hi.binding) or
        (x == slaves[0].unique_name and slaves[0].binding) or
        (x == slaves[1].unique_name and slaves[1].binding) or
        (x == slaves[2].unique_name and slaves[2].binding) or
        (x == slaves[3].unique_name and slaves[3].binding) or
        self.fail('unexpected name: %s' % x))
    self.sc.sgm.get_slave_at = (lambda i,x:
        (i == 0 and ((x == SlaveType.PERIPHERAL and slaves[0]) or
                     (x == SlaveType.MEMORY and slaves[1]))) or
        (i == 1 and ((x == SlaveType.PERIPHERAL and slaves[2]) or
                     (x == SlaveType.MEMORY and slaves[3]))) or
        self.fail('Unexpected: get_slave_at(%d,%s)' % (i,x)))
    self.sc.get_unique_name = (lambda x,y:
        (x == "Host Interface" and
         y == NodeType.HOST_INTERFACE and
         hi.unique_name) or
        self.fail("unexpected: get_unique_name(%s,%s)" % (x,y)))
    self.sc.get_number_of_slaves = (lambda x:
        (x == SlaveType.PERIPHERAL and 2) or
        (x == SlaveType.MEMORY and 2) or
        self.fail('Unexpected slave type: %d' % x))

    # Run.
    bind_dict = self.sc.get_master_bind_dict()

    # Test.
    self.assertEquals(len(bind_dict), sum(map(lambda x: len(x.binding),
        (hi, slaves[0], slaves[1], slaves[2], slaves[3]))))
    for k,v in hi.binding.iteritems():
      self.assertEqual(v, bind_dict[k])
    for slave in slaves:
      for k,v in slave.binding.iteritems():
        self.assertEqual(v, bind_dict[k])

  def test_set_project_location(self):
    '''Test "normal" functionality of set_project_location.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.set_project_location("p1_location")
    self.assertEqual(self.sc.project_tags['BASE_DIR'], "p1_location")

  def test_set_project_location_none(self):
    '''Test None passed to set_project_location.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.set_project_location(None)
    self.assertEqual(self.sc.project_tags['BASE_DIR'], None)

  def test_set_project_location_empty_str(self):
    '''Test "" passed to set_project_location.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.set_project_location('')
    self.assertEqual(self.sc.project_tags['BASE_DIR'], '')

  def test_get_project_location(self):
    '''Test "normal" functionality of get_project_location.'''
    self.sc.project_tags = { 'BASE_DIR': 'p1_location' }
    self.assertEqual(self.sc.get_project_location(), "p1_location")

  def test_get_project_location_none(self):
    '''Test None from get_project_location.'''
    self.sc.project_tags = { 'BASE_DIR': None }
    self.assertEqual(self.sc.get_project_location(), None)

  def test_get_project_location_empty_str(self):
    '''Test "" from get_project_location.'''
    self.sc.project_tags = { 'BASE_DIR': '' }
    self.assertEqual(self.sc.get_project_location(), "")

  def test_set_project_name(self):
    '''Test "normal" functionality of set_project_name.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.set_project_name("p1_name")
    self.assertEqual(self.sc.project_tags['PROJECT_NAME'], "p1_name")

  def test_set_project_name_none_raises_TypeError(self):
    '''Test None passed to set_project_name.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.assertRaises(TypeError, self.sc.set_project_name, None)

  def test_set_project_name_empty_str(self):
    '''Test "" passed to set_project_name.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.set_project_name('')
    self.assertEqual(self.sc.project_tags['PROJECT_NAME'], '')

  def test_get_project_name(self):
    '''Test "normal" functionality of get_project_name.'''
    self.sc.project_tags = { 'PROJECT_NAME': 'p1_name' }
    self.assertEqual(self.sc.get_project_name(), "p1_name")

  def test_get_project_name_none(self):
    '''Test None from get_project_name.'''
    self.sc.project_tags = { 'PROJECT_NAME': None }
    self.assertEqual(self.sc.get_project_name(), None)

  def test_get_project_name_empty_str(self):
    '''Test "" from get_project_name.'''
    self.sc.project_tags = { 'PROJECT_NAME': '' }
    self.assertEqual(self.sc.get_project_name(), "")

#  def test_set_vendor_tools(self):
#    '''Test "normal" functionality of set_vendor_tools.'''
#    self.sc.project_tags = self.EXAMPLE_CONFIG
#    self.sc.set_vendor_tools("toolchain")
#    self.assertEqual(self.sc.project_tags['build_tool'], "toolchain")
#
#  def test_set_vendor_tools_nothing_loaded_raises_error(self):
#    '''Tests that calling set_vendor_tools without having loaded a
#    configuration first raises an error.'''
#    self.assertRaises(StateError, self.sc.set_vendor_tools, 'foo')
#
#  def test_set_vendor_tools_none(self):
#    '''Test None passed to set_vendor_tools.'''
#    self.sc.project_tags = self.EXAMPLE_CONFIG
#    self.sc.set_vendor_tools(None)
#    self.assertEqual(self.sc.project_tags['build_tool'], None)
#
#  def test_set_vendor_tools_empty_str(self):
#    '''Test "" passed to set_vendor_tools.'''
#    self.sc.project_tags = self.EXAMPLE_CONFIG
#    self.sc.set_vendor_tools('')
#    self.assertEqual(self.sc.project_tags['build_tool'], '')

  def test_get_vendor_tools(self):
    '''Test "normal" functionality of get_vendor_tools.'''
    self.sc.board_dict = { 'build_tool': 'toolchain' }
    self.assertEqual(self.sc.get_vendor_tools(), "toolchain")

  def test_get_vendor_tools_nothing_loaded_raises_StateError(self):
    '''Tests that calling get_vendor_tools without having loaded a
    configuration first raises an error.'''
    self.assertRaises(StateError, self.sc.get_vendor_tools)

  def test_get_vendor_tools_none(self):
    '''Test None from get_vendor_tools.'''
    self.sc.board_dict = { 'build_tool': None }
    self.assertEqual(self.sc.get_vendor_tools(), None)

  def test_get_vendor_tools_empty_str(self):
    '''Test "" from get_vendor_tools.'''
    self.sc.board_dict = { 'build_tool': '' }
    self.assertEqual(self.sc.get_vendor_tools(), "")

  def test_set_board_name(self):
    '''Test "normal" functionality of set_board_name.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.get_board_config = mock.Mock(return_value=self.BOARD_CONFIG)
    self.sc.set_board_name("b1_name")
    self.assertEqual(self.sc.project_tags['board'], "b1_name")
    self.sc.get_board_config.assert_called_once_with('b1_name')

  def test_set_board_name_none_raises_TypeError(self):
    '''Test None passed to set_board_name.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.get_board_config = mock.Mock(side_effect=TypeError)
    self.assertRaises(TypeError, self.sc.set_board_name, None)
    self.sc.get_board_config.assert_called_once_with(None)

  def test_set_board_name_empty_str_raises_ValueError(self):
    '''Test "" passed to set_board_name.'''
    self.sc.project_tags = self.EXAMPLE_CONFIG
    self.sc.get_board_config = mock.Mock(side_effect=ValueError)
    self.assertRaises(ValueError, self.sc.set_board_name, '')
    self.sc.get_board_config.assert_called_once_with('')

  def test_get_board_name(self):
    '''Test "normal" functionality of get_board_name.'''
    self.sc.project_tags = { 'board': 'b1_name' }
    self.assertEqual(self.sc.get_board_name(), "b1_name")

  def test_get_board_name_nothing_loaded_returns_sycamore(self):
    '''Tests that calling get_board_name without having loaded a
    configuration first raises an error.'''
    self.assertEquals(self.sc.get_board_name(), 'sycamore1')

  def test_get_board_name_none(self):
    '''Test None from get_board_name.'''
    self.sc.project_tags = { 'board': None }
    self.assertEqual(self.sc.get_board_name(), None)

  def test_get_board_name_empty_str(self):
    '''Test "" from get_board_name.'''
    self.sc.project_tags = { 'board': '' }
    self.assertEqual(self.sc.get_board_name(), "")

  def test_get_board_constraint_filenames(self):
    board_name = 'boardnameyoyoyo'
    self.sc.project_tags = { 'board': board_name }
    self.sc.get_constraint_filenames = mock.Mock(
        return_value=self.BOARD_CONSTRAINT_FILES)
    self.assertEqual(self.sc.get_board_constraint_filenames(),
            self.BOARD_CONSTRAINT_FILES)
    self.sc.get_constraint_filenames.assert_called_once_with(board_name)

  def test_get_board_constraint_filenames_empty_okay(self):
    board_name = 'boardnameyoyoyo'
    self.sc.project_tags = { 'board': board_name }
    self.sc.get_constraint_filenames = mock.Mock(return_value=[])
    self.assertEqual(self.sc.get_board_constraint_filenames(), [])
    self.sc.get_constraint_filenames.assert_called_once_with(board_name)

  def test_add_project_constraint_file(self):
    self.sc.project_tags = { 'constraint_files': ['cons1'] }
    self.sc.add_project_constraint_file('cons2')
    self.assertEqual(self.sc.project_tags['constraint_files'],
        ['cons1', 'cons2'])

  def test_add_project_constraint_file_nothin_loaded_raises_StateError(self):
    self.assertRaises(StateError, self.sc.add_project_constraint_file('foo'))

  def test_add_project_constraint_file_already_added(self):
    self.sc.project_tags = { 'constraint_files': ['cons1', 'cons2'] }
    self.sc.add_project_constraint_file('cons2')
    self.assertEqual(self.sc.project_tags['constraint_files'],
        ['cons1', 'cons2'])

  def test_add_project_constraint_file_empty(self):
    self.sc.project_tags = { 'constraint_files': [] }
    self.sc.add_project_constraint_file('cons1')
    self.assertEqual(self.sc.project_tags['constraint_files'], ['cons1'])

  def test_add_project_constraint_file_none_raises_TypeError(self):
    self.sc.project_tags = { 'constraint_files': ['cons1', 'cons2'] }
    self.sc.add_project_constraint_file('cons1')
    self.assertRaises(TypeError, self.sc.add_project_constraint_file, None)

  def test_remove_project_constraint_file_first(self):
    self.sc.project_tags = { 'constraint_files': ['cons1', 'cons2', 'cons3'] }
    self.sc.remove_project_constraint_file('cons1')
    self.assertEquals(self.sc.project_tags['constraint_files'],
            ['cons2', 'cons3'])

  def test_remove_project_constraint_file_last(self):
    self.sc.project_tags = { 'constraint_files': ['cons1', 'cons2', 'cons3'] }
    self.sc.remove_project_constraint_file('cons3')
    self.assertEquals(self.sc.project_tags['constraint_files'],
            ['cons1', 'cons2'])

  def test_remove_project_constraint_file_middle(self):
    self.sc.project_tags = { 'constraint_files': ['cons1', 'cons2', 'cons3'] }
    self.sc.remove_project_constraint_file('cons2')
    self.assertEquals(self.sc.project_tags['constraint_files'],
            ['cons1', 'cons3'])

  def test_remove_project_constraint_file_dne(self):
    self.sc.project_tags = { 'constraint_files': ['cons1', 'cons2', 'cons3'] }
    self.sc.remove_project_constraint_file('cons4')
    self.assertEquals(self.sc.project_tags['constraint_files'],
            ['cons1', 'cons2', 'cons3'])

  def test_remove_project_constraint_file_empty(self):
    self.sc.project_tags = { 'constraint_files': [] }
    self.sc.remove_project_constraint_file('cons4')
    self.assertEquals(self.sc.project_tags['constraint_files'], [])

  def test_set_project_constraint_files(self):
    self.sc.project_tags = { 'constraint_files': [] }
    self.sc.set_project_constraint_files(self.BOARD_CONSTRAINT_FILES)
    self.assertEqual(self.BOARD_CONSTRAINT_FILES,
        self.sc.project_tags['constraint_files'])

  def test_set_project_constraint_files_overwrite(self):
    self.sc.project_tags = { 'constraint_files': ['foo', 'bar', 'baz'] }
    self.sc.set_project_constraint_files(self.BOARD_CONSTRAINT_FILES)
    self.assertEqual(self.BOARD_CONSTRAINT_FILES,
        self.sc.project_tags['constraint_files'])

  def test_set_project_constraint_files_none_raises_TypeError(self):
    self.sc.project_tags = { 'constraint_files': ['foo', 'bar', 'baz'] }
    self.assertRaises(TypeError, self.sc.set_project_constraint_files, None)

  def test_set_project_constraint_files_empty_str_raises_TypeError(self):
    self.sc.project_tags = { 'constraint_files': ['foo', 'bar', 'baz'] }
    self.assertRaises(TypeError, self.sc.set_project_constraint_files, '')

  def test_get_project_constraint_files(self):
    self.sc.project_tags = {
        'constraint_files': self.BOARD_CONSTRAINT_FILES
    }
    self.assertEqual(self.sc.get_project_constraint_files(),
        self.BOARD_CONSTRAINT_FILES)

  def test_get_project_constraint_files_pt_empty(self):
    self.sc.project_tags = {}
    self.sc.board_dict = {
        'default_constraint_files': self.BOARD_CONSTRAINT_FILES
    }
    self.assertEqual(self.sc.get_project_constraint_files(),
        self.BOARD_CONSTRAINT_FILES)

  def test_get_project_constraint_files_board_config_not_loaded_raises_StateError(self):
    self.sc.project_tags = {}
    self.assertRaises(StateError, self.sc.get_project_constraint_files)

  def test_get_fpga_part_number(self):
    self.sc.board_dict = { 'fpga_part_number': 'number' }
    self.assertEqual(self.sc.get_fpga_part_number(), 'number')

  def test_get_fpga_part_number_nothing_loaded_raises_StateError(self):
    self.assertRaises(StateError, self.sc.get_fpga_part_number)

  def test_new_design(self):
    sgm = mock.Mock()
    self.sc.new_sgm = mock.Mock(return_value=sgm)
    self.sc.new_design()
    self.sc.new_sgm.assert_called_once_with()
    self.assertEqual(self.sc.sgm, sgm)
    self.assertEqual(self.sc.tags, {})
    self.assertEqual(self.sc.file_name, '')
    self.assertEqual(self.sc.project_tags, self.NEW_CONFIG)

  def test_set_bus_type(self):
    self.sc.set_bus_type('Wishbone')
    self.assertEqual('Wishbone', self.sc.bus_type)

  def test_set_bus_type_none_raises_TypeError(self):
    self.assertRaises(TypeError, self.sc.set_bus_type, None)

  def test_set_bus_type_bad_raises_ValueError(self):
    self.assertRaises(ValueError, self.sc.set_bus_type, 'bad')

  def test_set_bus_type_wishbone(self):
    self.sc.set_bus_type('Wishbone')
    self.assertEqual(self.sc.bus_type, 'Wishbone')

  def test_set_bus_type_axie(self):
    self.sc.set_bus_type('Axie')
    self.assertEqual(self.sc.bus_type, 'Axie')

  def test_set_host_interface(self):
    unique_name = 'uniquename'
    self.sc.get_unique_name = mock.Mock(return_value=unique_name)

    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_node_names = mock.Mock(return_value=['foo', 'bar', 'baz'])
    self.sc.sgm.add_node = mock.Mock()

    # Args:
    arg_hin = 'host-iface-name'

    sf = mock.Mock()
    sf.find_module_filename = mock.Mock(return_value='fname1')
    self.sc.find_rtl_file_location = mock.Mock(return_value='fname2')
    self.sc.new_sf = lambda: sf

    params = ['p1', 'p2', 'p3']
    self.sc.get_bus_type = lambda: 'bus_type'
    self.sc.get_module_tags = mock.Mock(return_value=params)
    self.sc.sgm.set_parameters = mock.Mock()

    self.assertTrue(self.sc.set_host_interface(arg_hin))
    self.sc.get_unique_name.assert_called_once_with(
        'Host Interface', NodeType.HOST_INTERFACE)
    self.sc.sgm.add_node.assert_called_once_with(
        'Host Interface', NodeType.HOST_INTERFACE)
    sf.find_module_filename.assert_called_once_with(arg_hin)
    self.sc.find_rtl_file_location.assert_called_once_with('fname1')
    self.sc.get_module_tags.assert_called_once_with(
        filename='fname2', bus='bus_type')
    self.sc.sgm.set_parameters.assert_called_once_with(unique_name, params)

  def test_set_host_interface_adds_new_hi(self):
    uname = 'unique1'
    self.sc.get_unique_name = mock.Mock(return_value=uname)
    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_node_names = mock.Mock(return_value=['foo', 'bar', 'baz'])
    self.sc.sgm.add_node = mock.Mock()

    # Fill-in functions that we're not testing here, but are overridden to make
    # the unit test quicker.
    self.sc.sgm.set_parameters = mock.Mock(return_value=None)
    sf = mock.Mock()
    sf.find_module_filename = mock.Mock(return_value='fname1')
    self.sc.new_sf = mock.Mock(return_value=sf)
    self.sc.find_rtl_file_location = mock.Mock(return_value='fname2')
    self.sc.get_module_tags = mock.Mock(return_value=['a', 'b'])
    self.sc.get_bus_type = mock.Mock(return_value=None)

    # Assertions (& test-part).
    self.assertTrue(self.sc.set_host_interface('arg-hin'))
    self.sc.get_unique_name.assert_called_once_with('Host Interface',
        NodeType.HOST_INTERFACE)
    self.sc.sgm.add_node.assert_called_once_with('Host Interface',
        NodeType.HOST_INTERFACE)

  def test_set_host_interface_doesnt_add_existing_hi(self):
    uname = 'foo'
    self.sc.get_unique_name = mock.Mock(return_value=uname)
    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_node_names = mock.Mock(return_value=['foo', 'bar', 'baz'])
    self.sc.sgm.add_node = mock.Mock(
        side_effect=AssertionError('Should not call, %s already added' % uname))

    # Fill-in functions that we're not testing here.
    self.sc.sgm.set_parameters = mock.Mock(return_value=None)
    sf = mock.Mock()
    sf.find_module_filename = mock.Mock(return_value='fname1')
    self.sc.new_sf = mock.Mock(return_value=sf)
    self.sc.find_rtl_file_location = mock.Mock(return_value='fname2')
    self.sc.get_module_tags = mock.Mock(return_value=['a', 'b'])
    self.sc.get_bus_type = mock.Mock(return_value=None)

    # Assertions (& test-part).
    self.assertTrue(self.sc.set_host_interface('arg-hin'))
    self.sc.get_unique_name.assert_called_once_with('Host Interface',
        NodeType.HOST_INTERFACE)

  def test_set_host_interface_raises_ModuleNotFound(self):
    uname = 'unique1'
    self.sc.get_unique_name = mock.Mock(return_value=uname)
    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_node_names = mock.Mock(return_value=['foo', 'bar', 'baz'])
    self.sc.sgm.add_node = mock.Mock()

    # Fill-in functions that we're not testing here, but are overridden to make
    # the unit test quicker.
    self.sc.sgm.set_parameters = mock.Mock(return_value=None)
    sf = mock.Mock()
    sf.find_module_filename = mock.Mock(return_value='fname1')
    self.sc.new_sf = mock.Mock(return_value=sf)
    self.sc.find_rtl_file_location = mock.Mock(return_value='fname2')
    self.sc.get_module_tags = mock.Mock(return_value=['a', 'b'])
    self.sc.get_bus_type = mock.Mock(return_value=None)

    # Test and Assert.
    self.assertTrue(self.sc.set_host_interface('arg-hin'))
    self.sc.get_unique_name.assert_called_once_with('Host Interface',
        NodeType.HOST_INTERFACE)
    self.sc.sgm.add_node.assert_called_once_with('Host Interface',
        NodeType.HOST_INTERFACE)

  def test_rename_slave(self):
    slave_type, index, new_name = SlaveType.PERIPHERAL, 4, 'name'
    self.sc.sgm = mock.Mock()
    self.sc.sgm.rename_slave = mock.Mock()
    self.sc.rename_slave(slave_type, index, new_name)
    self.sc.sgm.rename_slave.assert_called_once_with(
        slave_type, index, new_name)

  def test_rename_slave_raises_idx_TypeError(self):
    slave_type, index, new_name = SlaveType.PERIPHERAL, 'foo', 'name'
    self.sc.sgm = mock.Mock()
    self.sc.sgm.rename_slave = mock.Mock(side_effect=TypeError)
    self.assertRaises(TypeError, self.sc.rename_slave,
        slave_type, index, new_name)
    self.sc.sgm.rename_slave.assert_called_once_with(
        slave_type, index, new_name)

  def test_rename_slave_raises_none_TypeError(self):
    slave_type, index, new_name = SlaveType.PERIPHERAL, 2, None
    self.sc.sgm = mock.Mock()
    self.sc.sgm.rename_slave = mock.Mock(side_effect=TypeError)
    self.assertRaises(TypeError, self.sc.rename_slave,
        slave_type, index, new_name)
    self.sc.sgm.rename_slave.assert_called_once_with(
        slave_type, index, new_name)

  def test_rename_slave_raises_str_TypeError(self):
    slave_type, index, new_name = 'peripheral', 2, None
    self.sc.sgm = mock.Mock()
    self.sc.sgm.rename_slave = mock.Mock(side_effect=TypeError)
    self.assertRaises(TypeError, self.sc.rename_slave,
        slave_type, index, new_name)
    self.sc.sgm.rename_slave.assert_called_once_with(
        slave_type, index, new_name)

  def test_add_slave_peripheral(self):
    arg_n, arg_f, arg_st, arg_si = 'name', '/tmp/name', SlaveType.PERIPHERAL, 2

    mock_slaves = []
    for i in xrange(3):
      mock_slaves.append(mock.Mock())
      mock_slaves[-1].slave_index = i
    num_slaves = len(mock_slaves)

    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_number_of_slaves = mock.Mock(return_value=num_slaves)
    self.sc.sgm.add_node = mock.Mock()
    self.sc.sgm.get_number_of_peripheral_slaves = mock.Mock(
        return_value=num_slaves)
    self.sc.get_unique_name = mock.Mock(return_value='uname')
    self.sc.sgm.get_node = mock.Mock(return_value=mock_slaves[-1])
    self.sc.sgm.move_peripheral_slave = mock.Mock(
        side_effect=AssertionError('Should not be called.'))
    mock_params = { 'parameters': { 'p1': '1', 'p2': '2' } }
    self.sc.bus_type = 'bustype'
    self.sc.get_module_tags = mock.Mock(return_value=mock_params)
    self.sc.sgm.set_parameters = mock.Mock()
    self.sc.project_tags = { 'SLAVES': { 'parameters': { 'p1': '-1' } } }

    # Run & Test.
    self.assertEquals(self.sc.add_slave(arg_n, arg_f, arg_st, arg_si), 'uname')
    self.sc.sgm.get_number_of_slaves.assert_called_once_with(arg_st)
    self.sc.sgm.add_node.assert_called_once_with(arg_n, NodeType.SLAVE, arg_st)
    self.sc.sgm.get_number_of_peripheral_slaves.assert_called_once_with()
    self.sc.get_unique_name.assert_called_with(
        arg_n, NodeType.SLAVE, arg_st, num_slaves - 1)
    self.sc.sgm.get_node.assert_called_with('uname')
    self.sc.get_module_tags.assert_called_once_with(arg_f, 'bustype')
    self.sc.sgm.set_parameters.assert_called_once_with('uname', mock_params)
    self.assertEquals(mock_params, { 'parameters': { 'p1': '1', 'p2': '2' } })

  def test_add_slave_memory(self):
    arg_n, arg_f, arg_st, arg_si = 'name', '/tmp/name', SlaveType.MEMORY, 2

    mock_slaves = []
    for i in xrange(3):
      mock_slaves.append(mock.Mock())
      mock_slaves[-1].slave_index = i
    num_slaves = len(mock_slaves)

    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_number_of_slaves = mock.Mock(return_value=num_slaves)
    self.sc.sgm.add_node = mock.Mock()
    self.sc.sgm.get_number_of_memory_slaves = mock.Mock(
        return_value=num_slaves)
    self.sc.get_unique_name = mock.Mock(return_value='uname')
    self.sc.sgm.get_node = mock.Mock(return_value=mock_slaves[-1])
    self.sc.sgm.move_slave = mock.Mock(
        side_effect=AssertionError('Should not be called.'))
    mock_params = { 'parameters': { 'p1': '1', 'p2': '2' } }
    self.sc.bus_type = 'bustype'
    self.sc.get_module_tags = mock.Mock(return_value=mock_params)
    self.sc.sgm.set_parameters = mock.Mock()
    self.sc.project_tags = { 'SLAVES': { 'parameters': { 'p1': '-1' } } }

    # Run & Test.
    self.assertEquals(self.sc.add_slave(arg_n, arg_f, arg_st, arg_si), 'uname')
    self.sc.sgm.get_number_of_slaves.assert_called_once_with(arg_st)
    self.sc.sgm.add_node.assert_called_once_with(arg_n, NodeType.SLAVE, arg_st)
    self.sc.sgm.get_number_of_memory_slaves.assert_called_once_with()
    self.sc.get_unique_name.assert_called_with(
        arg_n, NodeType.SLAVE, arg_st, num_slaves - 1)
    self.sc.sgm.get_node.assert_called_with('uname')
    self.sc.get_module_tags.assert_called_once_with(arg_f, 'bustype')
    self.sc.sgm.set_parameters.assert_called_once_with('uname', mock_params)
    self.assertEquals(mock_params, { 'parameters': { 'p1': '1', 'p2': '2' } })

  def test_add_slave_peripheral_0_not_DRT_raises_SlaveError(self):
    arg_n, arg_f, arg_st, arg_si = 'name', '/tmp/name', SlaveType.PERIPHERAL, 0

    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_number_of_slaves = mock.Mock(return_value=0)
    self.sc.sgm.add_node = mock.Mock()

    self.assertRaises(SlaveError, self.sc.add_slave, arg_n, arg_f, arg_st, arg_si)
    self.sc.sgm.get_number_of_slaves.assert_called_once_with(arg_st)
    self.sc.sgm.add_node.assert_called_once_with(arg_n, NodeType.SLAVE, arg_st)

  def test_add_slave_peripheral_0_DRT_ok(self):
    arg_n, arg_f, arg_st, arg_si = 'DRT', '/tmp/name', SlaveType.PERIPHERAL, 0

    mock_slaves = []
    for i in xrange(1):
      mock_slaves.append(mock.Mock())
      mock_slaves[-1].slave_index = i
    num_slaves = 0

    self.sc.sgm = mock.Mock()
    self.sc.sgm.get_number_of_slaves = mock.Mock(return_value=num_slaves)
    self.sc.sgm.add_node = mock.Mock()
    self.sc.sgm.get_number_of_peripheral_slaves = mock.Mock(
        return_value=num_slaves)
    self.sc.get_unique_name = mock.Mock(return_value='uname')
    self.sc.sgm.get_node = mock.Mock(return_value=mock_slaves[-1])
    self.sc.sgm.move_peripheral_slave = mock.Mock(
        side_effect=AssertionError('Should not be called.'))
    mock_params = { 'parameters': { 'p1': '1', 'p2': '2' } }
    self.sc.bus_type = 'bustype'
    self.sc.get_module_tags = mock.Mock(return_value=mock_params)
    self.sc.sgm.set_parameters = mock.Mock()
    self.sc.project_tags = { 'SLAVES': { 'parameters': { 'p1': '-1' } } }

    # Run & Test.
    self.assertEquals(self.sc.add_slave(arg_n, arg_f, arg_st, arg_si), 'uname')
    self.sc.sgm.get_number_of_slaves.assert_called_once_with(arg_st)
    self.sc.sgm.add_node.assert_called_once_with(arg_n, NodeType.SLAVE, arg_st)
    self.sc.sgm.get_number_of_peripheral_slaves.assert_called_once_with()
    self.sc.get_unique_name.assert_called_with(arg_n, NodeType.SLAVE, arg_st, 0)
    self.sc.sgm.get_node.assert_called_with('uname')
    self.sc.get_module_tags.assert_called_once_with(arg_f, 'bustype')
    self.sc.sgm.set_parameters.assert_called_once_with('uname', mock_params)
    self.assertEquals(mock_params, { 'parameters': { 'p1': '1', 'p2': '2' } })

  def test_get_unique_name(self):
    pass

  def test_add_slave(self):
    pass

  def test_remove_slave(self):
    pass

  def test_move_slave_in_peripheral_bus(self):
    pass

  def test_move_slave_in_memory_bus(self):
    pass

  def test_move_slave_between_bus(self):
    pass

  def test_arbitration(self):
    pass

  def test_get_connected_arbitration_slave(self):
    pass

  def test_remove_arbitration_by_arbitrator(self):
    pass

  def test_save_config_file(self):
    pass



class IntTest(unittest.TestCase):
  """Integration tests for sap_controller.py"""
  def setUp(self):
    self.dbg = False
    self.vbs = False
    if "SAPLIB_VERBOSE" in os.environ:
      if (os.environ["SAPLIB_VERBOSE"] == "True"):
        self.vbs = True
    if "SAPLIB_DEBUG" in os.environ:
      if (os.environ["SAPLIB_DEBUG"] == "True"):
        self.dbg = True

    # Every test needs the SGC.
    self.sc = sc.SapController()
    return

  def test_load_config_file(self):
    # Find a file to load
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    board_name = self.sc.get_board_name()

    self.assertEqual(board_name, "xilinx-s3esk")

  def test_generate_project(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)

    home_dir = saputils.resolve_linux_path("~")
    self.sc.save_config_file(home_dir + "/test_out.json")

    self.sc.set_config_file_location(home_dir + "/test_out.json")
    self.sc.generate_project()

    # FIXME: How do I actually test out the project generation?
    self.assertEqual(True, True)

  def test_get_master_bind_dict(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()
    bind_dict = self.sc.get_master_bind_dict()

#    for key in bind_dict.keys():
#      print "key: " + key

    self.assertIn("phy_uart_in", bind_dict.keys())

  def test_project_location(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.set_project_location("p1_location")
    result = self.sc.get_project_location()

    self.assertEqual(result, "p1_location")

  def test_project_name(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.set_project_name("p1_name")
    result = self.sc.get_project_name()

    self.assertEqual(result, "p1_name")

  def test_vendor_tools(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)

#    self.sc.set_vendor_tools("altera")
    result = self.sc.get_vendor_tools()
    self.assertEqual(result, "xilinx")

  def test_board_name(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)

    self.sc.set_board_name("bored of writing unit tests")
    result = self.sc.get_board_name()
    self.assertEqual(result, "bored of writing unit tests")

  def test_constraint_filename(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    result = self.sc.get_board_constraint_filenames()
    self.assertEqual(result[0], "s3esk_sycamore.ucf")

  def test_add_remove_constraint(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.add_project_constraint_file("test file")
    result = self.sc.get_project_constraint_files()
    self.assertIn("test file", result)
    self.sc.remove_project_constraint_file("test file")

    result = self.sc.get_project_constraint_files()
    self.assertNotIn("test file", result)

#  def test_fpga_part_number(self):
#    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
#    self.sc.load_config_file(file_name)
#
#    self.sc.set_fpga_part_number("bored of writing unit tests")
#    result = self.sc.get_fpga_part_number()
#    self.assertEqual(result, "bored of writing unit tests")

  def test_initialize_graph(self):
    #load a file
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    slave_count = self.sc.get_number_of_peripheral_slaves()

    self.assertEqual(slave_count, 2)

  def test_get_number_of_slaves(self):
    # Load a file.
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    self.sc.add_slave("mem1", file_name, SlaveType.MEMORY)

    p_count = self.sc.get_number_of_slaves(SlaveType.PERIPHERAL)
    m_count = self.sc.get_number_of_slaves(SlaveType.MEMORY)
    self.assertEqual(p_count, 2)
    self.assertEqual(m_count, 1)

  def test_apply_stave_tags_to_project(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/arb_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()
    # This example only attaches one of the two arbitrators.

    # Attach the second arbitrator.
    filename = saputils.find_rtl_file_location("tft.v")
    slave_name = self.sc.add_slave("tft1", filename, SlaveType.PERIPHERAL)

    host_name = self.sc.sgm.get_slave_name_at(SlaveType.PERIPHERAL, 1)
    arb_master = "lcd"

    self.sc.add_arbitrator_by_name(host_name, arb_master, slave_name)

    # Add a binding for the tft screen.
    self.sc.set_binding(slave_name, "data_en", "lcd_e")

    # Now we have something sigificantly different than what was loaded in.
    self.sc.set_project_name("arbitrator_project")
    self.sc.apply_slave_tags_to_project()
    pt = self.sc.project_tags

    # Check to see if the new slave took.
    self.assertIn("tft1", pt["SLAVES"].keys())

    # Check to see if the arbitrator was set up.
    self.assertIn("lcd", pt["SLAVES"]["console"]["BUS"].keys())

    # Check to see if the arbitrator is attached to the slave.
    self.assertEqual("tft1", pt["SLAVES"]["console"]["BUS"]["lcd"])

    # Check to see if the binding was written.
    self.assertIn("data_en", pt["SLAVES"]["tft1"]["bind"].keys())

    home_dir = saputils.resolve_linux_path("~")
    self.sc.save_config_file(home_dir + "/arb_test_out.json")

  def test_set_host_interface(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    self.sc.set_host_interface("ft_host_interface")
    name = self.sc.get_host_interface_name()

    self.assertEqual(name, "ft_host_interface")

  def test_bus_type(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    bus_name = self.sc.get_bus_type()

    self.assertEqual(bus_name, "wishbone")

  def test_rename_slave(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    filename = saputils.find_rtl_file_location("wb_console.v")

    self.sc.rename_slave(SlaveType.PERIPHERAL, 1, "name1")

    name = self.sc.get_slave_name(SlaveType.PERIPHERAL, 1)

    self.assertEqual(name, "name1")

  def test_add_slave(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    self.sc.add_slave("mem1", None, SlaveType.MEMORY)

    p_count = self.sc.get_number_of_slaves(SlaveType.PERIPHERAL)
    m_count = self.sc.get_number_of_slaves(SlaveType.MEMORY)
    self.assertEqual(p_count, 2)
    self.assertEqual(m_count, 1)

  def test_remove_slave(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    self.sc.remove_slave(SlaveType.PERIPHERAL, 1)
    p_count = self.sc.get_number_of_slaves(SlaveType.PERIPHERAL)
    self.assertEqual(p_count, 1)

  def test_move_slave_in_peripheral_bus(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()
    filename = saputils.find_rtl_file_location("wb_console.v")

    self.sc.add_slave("test", filename, SlaveType.PERIPHERAL)

    name1 = self.sc.get_slave_name(SlaveType.PERIPHERAL, 2)
    self.sc.move_slave("test",
                       SlaveType.PERIPHERAL, 2,
                       SlaveType.PERIPHERAL, 1)

    name2 = self.sc.get_slave_name(SlaveType.PERIPHERAL, 1)
    self.assertEqual(name1, name2)

  def test_move_slave_in_memory_bus(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    filename = saputils.find_rtl_file_location("wb_console.v")
    self.sc.add_slave("test1", filename, SlaveType.MEMORY)
    self.sc.add_slave("test2", filename, SlaveType.MEMORY)

    m_count = self.sc.get_number_of_slaves(SlaveType.MEMORY)

    name1 = self.sc.get_slave_name(SlaveType.MEMORY, 0)
    self.sc.move_slave("test1",
                       SlaveType.MEMORY, 0,
                       SlaveType.MEMORY, 1)

    name2 = self.sc.get_slave_name(SlaveType.MEMORY, 1)
    self.assertEqual(name1, name2)

  def test_move_slave_between_bus(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()
    filename = saputils.find_rtl_file_location("wb_console.v")

    self.sc.add_slave("test", filename, SlaveType.PERIPHERAL)

    name1 = self.sc.get_slave_name(SlaveType.PERIPHERAL, 2)
    self.sc.move_slave("test",
                       SlaveType.PERIPHERAL, 2,
                       SlaveType.MEMORY, 0)

    name2 = self.sc.get_slave_name(SlaveType.MEMORY, 0)
    self.assertEqual(name1, name2)

  def test_arbitration(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/arb_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    # TODO Test if the arbitrator can be removed
    p_count = self.sc.get_number_of_slaves(SlaveType.PERIPHERAL)
    m_count = self.sc.get_number_of_slaves(SlaveType.MEMORY)

    arb_host = ""
    arb_slave = ""
    bus_name = ""

    back = self.dbg
#    self.dbg = True

    for i in xrange(p_count):
      name1 = self.sc.get_slave_name(SlaveType.PERIPHERAL, i)
      if self.dbg:
        print "testing %s for arbitration..." % (name1)
      if self.sc.is_active_arbitrator_host(SlaveType.PERIPHERAL, i):
        arb_host = name1
        a_dict = self.sc.get_arbitrator_dict(SlaveType.PERIPHERAL, i)
        for key in a_dict.keys():
          bus_name = key
          arb_slave = a_dict[key]

    for i in xrange(m_count):
      name1 = self.sc.get_slave_name(SlaveType.MEMORY, i)
      if self.sc.is_active_arbitrator_host(SlaveType.MEMORY, i):
        arb_host = name1
        a_dict = self.sc.get_arbitrator_dict(SlaveType.MEMORY, i)
        for key in a_dict.keys():
          bus_name = key
          arb_slave = a_dict[key]

    arb_slave_name = self.sc.get_slave_name_by_unique(arb_slave)
    if self.dbg:
      print "%s is connected to %s through %s" % (arb_host, arb_slave_name, bus_name)

    self.dbg = False
    self.assertEqual(arb_host, "console")
    self.assertEqual(arb_slave_name, "mem1")
    self.assertEqual(bus_name, "fb")

  def test_get_connected_arbitration_slave(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/arb_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    # TODO Test if the arbitrator can be removed
    p_count = self.sc.get_number_of_slaves(SlaveType.PERIPHERAL)
    m_count = self.sc.get_number_of_slaves(SlaveType.MEMORY)

    arb_host = ""
    arb_slave = ""
    bus_name = ""
    host_name = ""

    back = self.dbg
#    self.dbg = True

    for i in xrange(p_count):
      name1 = self.sc.get_slave_name(SlaveType.PERIPHERAL, i)
      if self.dbg:
        print "testing %s for arbitration..." % (name1)
      if self.sc.is_active_arbitrator_host(SlaveType.PERIPHERAL, i):
        arb_host = name1
        host_name = self.sc.sgm.get_slave_at(SlaveType.PERIPHERAL, i).unique_name
        a_dict = self.sc.get_arbitrator_dict(SlaveType.PERIPHERAL, i)
        for key in a_dict.keys():
          bus_name = key
          arb_slave = a_dict[key]

    for i in xrange(m_count):
      name1 = self.sc.get_slave_name(SlaveType.MEMORY, i)
      if self.sc.is_active_arbitrator_host(SlaveType.MEMORY, i):
        host_name = self.sc.sgm.get_slave_at(SlaveType.PERIPHERAL, i).unique_name
        arb_host = name1
        a_dict = self.sc.get_arbitrator_dict(SlaveType.MEMORY, i)
        for key in a_dict.keys():
          bus_name = key
          arb_slave = a_dict[key]

    arb_slave_name = self.sc.get_slave_name_by_unique(arb_slave)

    if self.dbg:
      print "%s is connected to %s through %s" % (arb_host, arb_slave_name, bus_name)

    slave_name = self.sc.get_connected_arbitrator_slave(host_name, bus_name)
    self.dbg = False
    self.assertEqual(slave_name, "mem1_0_0")

  def test_remove_arbitration_by_arbitrator(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/arb_example.json"
    self.sc.load_config_file(file_name)
    self.sc.initialize_graph()

    # TODO Test if the arbitrator can be removed
    p_count = self.sc.get_number_of_slaves(SlaveType.PERIPHERAL)
    m_count = self.sc.get_number_of_slaves(SlaveType.MEMORY)

    arb_host = ""
    arb_slave = ""
    bus_name = ""
    host_name = ""

    back = self.dbg
#    self.dbg = True

    for i in xrange(p_count):
      name1 = self.sc.get_slave_name(SlaveType.PERIPHERAL, i)
      if self.dbg:
        print "testing %s for arbitration..." % (name1)
      if self.sc.is_active_arbitrator_host(SlaveType.PERIPHERAL, i):
        arb_host = name1
        host_name = self.sc.sgm.get_slave_at(SlaveType.PERIPHERAL, i).unique_name
        a_dict = self.sc.get_arbitrator_dict(SlaveType.PERIPHERAL, i)
        for key in a_dict.keys():
          bus_name = key
          arb_slave = a_dict[key]

    for i in xrange(m_count):
      name1 = self.sc.get_slave_name(SlaveType.MEMORY, i)
      if self.sc.is_active_arbitrator_host(SlaveType.MEMORY, i):
        host_name = self.sc.sgm.get_slave_at(SlaveType.PERIPHERAL, i).unique_name
        arb_host = name1
        a_dict = self.sc.get_arbitrator_dict(SlaveType.MEMORY, i)
        for key in a_dict.keys():
          bus_name = key
          arb_slave = a_dict[key]

    arb_slave_name = self.sc.get_slave_name_by_unique(arb_slave)

    if self.dbg:
      print "%s is connected to %s through %s" % (arb_host, arb_slave_name, bus_name)

    slave_name = self.sc.get_connected_arbitrator_slave(host_name, bus_name)
    self.dbg = False
    self.assertEqual(slave_name, "mem1_0_0")

    self.sc.remove_arbitrator_by_arb_master(host_name, bus_name)

    slave_name = self.sc.get_connected_arbitrator_slave(host_name, bus_name)
    self.assertIsNone(slave_name)

  def test_save_config_file(self):
    file_name = os.getenv("SAPLIB_BASE") + "/example_project/gpio_example.json"
    self.sc.load_config_file(file_name)

    home_dir = saputils.resolve_linux_path("~")
    self.sc.save_config_file(home_dir + "/test_out.json")
    try:
      filein = open(home_dir + "/test_out.json")
      json_string = filein.read()
      filein.close()
    except IOError as err:
      print ("File Error: " + str(err))
      self.assertEqual(True, False)

    self.assertEqual(True, True)

if __name__ == "__main__":
  unittest.main()

