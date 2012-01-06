//protocol_template.c

/*
Distributed under the MIT licesnse.
Copyright (c) 2011 Dave McCoy (dave.mccoy@cospandesign.com)

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in 
the Software without restriction, including without limitation the rights to 
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
of the Software, and to permit persons to whom the Software is furnished to do 
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all 
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
SOFTWARE.
*/


#include <linux/kernel.h>
#include <linux/slab.h>
#include <linux/workqueue.h>
#include "../sycamore/sycamore_protocol.h"
#include "../sycamore/sycamore_bus.h"
#include "../sycamore/sycamore_commands.h"


#define READ_IDLE 			0
#define READ_SIZE 			1
#define READ_COMMAND 		2
#define READ_ADDRESS 		3
#define READ_DATA 			4

#define READ_BUF_SIZE		4

#define ENCODED_BUF_SIZE	512

typedef struct _encoded_buffer_t encoded_buffer_t;

struct _encoded_buffer_t {
	u32 encoded_buf_size;
	u8 encoded_buffer[ENCODED_BUF_SIZE];
};

struct _sycamore_protocol_t {
	//protocol specific data
	void * protocol;

	sycamore_bus_t sb;

	//hardware comm
	hardware_write_func_t write_func;
	void * write_data;

	//write data
	u32 write_command;
	u32 write_out_count;
	u32 write_out_offset;
	u32 write_buffer_size;
	u8 *write_buffer;
	struct work_struct write_work;

	u32 hw_bytes_left;

	
	int current_buffer;
	encoded_buffer_t encoded_buffer[2];


	//read information
	int read_state;
	u32 read_command;
	u32	read_data;
	u32 read_size;
	u32 read_data_count;
	u32 read_data_pos;
	u32 read_address;
	u32 read_device_address;
	u32 read_pos;

	u8 read_out_data[READ_BUF_SIZE];

};



//local function prototypes
//sets up everything for a write to the hardware
int hardware_write (
				sycamore_protocol_t * sp,
				u32 command,
				u8 device_address,
				u32 offset,
				char * buffer,
				u32 length);


void write_work(struct work_struct *work);
void encode_buffer(sycamort_protocol_t *sp);

/**
 * protocol_template
 * Description: Modify this file to adapt a new hardware interconnect
 *
 */

typedef struct _my_protocol_t my_protocol_t;

struct _my_protocol_t {
	//update this variable to reflect the status of the command
	int command_status;
};



/**
 * sycamore_protocol_init
 * Description: initialize the hardware specific protocol
 *	modify the between CUSTOM_START, CUSTOM_END
 *
 * Return:
 *	returns an initialized sycamore_protocol_t structure
 *	NULL on failue
 **/
sycamore_protocol_t * sp_init(void){
	//don't change!	
	sycamore_protocol_t *sp = NULL;
	my_protocol_t *mp = NULL;

	printk("%s: initializing the protocol specific driver\n", __func__);
	//allocate space for the sycamore_protocol_t structure
	sp = (sycamore_protocol_t *) kzalloc(sizeof(sycamore_protocol_t), GFP_KERNEL);
	if (sp == NULL){
		//failed to allocate memory for sycamore_protocol
		goto fail2;
	}
	//allocate space for your specific protocol here
	mp = (my_protocol_t *) kzalloc(sizeof(my_protocol_t), GFP_KERNEL);
	if (mp == NULL){
		//failed to allocate memory for my_protocol_t
		goto fail1;
	}


	sp->write_data			= NULL;
	sp->write_func			= NULL;

	INIT_WORK(&sp->write_work, write_work);

	sp->write_out_count		= 0;
	sp->write_out_size		= 0;

	sp->read_command 		= 0;
	sp->read_size 			= 0;
	sp->read_data			= 0;
	sp->read_data_count		= 0;
	sp->read_data_pos		= 0;
	sp->read_pos			= 0;
	sp->read_address 		= 0;
	sp->read_device_address	= 0;
	sp->read_state			= READ_IDLE;
	memset (&sp->write_buffer[0], 0, WRITE_BUF_SIZE);
	memset (&sp->read_out_data[0], 0, READ_BUF_SIZE);
	//CUSTOM_START

	//initialize your variables here

	//CUSTOM_END
	return sp;

fail1:
	kfree(sp);
fail2:
	return NULL;
}


/**
 * sycamore_destroy
 * Description: cleans and removes anything that was done within init
 *
 * Return:
 *	nothing
 **/
void sp_destroy(sycamore_protocol_t *sp){
	//CUSTOM_START
	//stop anything you need to stop here, deallocate anything here
	//CUSTOM_END
	//free the custom protocol stuff
		

	cancel_work_sync(&sp->write_work);

	kfree(sp->protocol);
	kfree(sp);
}

/**
 * sp_set_write_function
 * Description: sets the driver specific write function, this is what
 *	all the functions will use to write to the FPGA
 *
 * Return:
 *	nothing
 **/
void sp_set_write_function(
						sycamore_protocol_t *sp, 
						hardware_write_func_t write_func, 
						void *data){
	printk("%s: setting the write function to %p\n", __func__, write_func);
	sp->write_func = write_func;
	sp->write_data = data;
}


/**
 * write_work
 * Desciption: bottom half interrupts so that the heavly lifting
 *	of writing to the hardware driver isn't done within a interrupt
 *	context
 *
 * Return:
 *	nothing
 **/
void write_work(struct work_struct *work){
	sycamore_protocol_t *sp = NULL;
	u32 current_offset = 0;
	u32 buffer_length = 0;
	u8 * buffer;
	printk("%s: entered\n", __func__);
	sp = container_of(work, sycamore_protocol_t, write_work);

	//localize everything so that it's just easier to read
	buffer_length = sp->encoded_buffer[sp->current_buffer].encoded_buf_size;
	buffer = &sp->encoded_buffer[sp->current_buffer].encoded_buffer[0];

	sp->write_out_offset += sp->write_out_count;
	
	if (sp->write_out_offset < buffer_length){
		//got more data to send out
		printk("sending the rest of the data (%d more bytes)\n", buffer_length - sp->write_out_count);	
		sp->write_out_count += sp->write_func(
								sp->write_data, 
								&buffer[sp->write_out_offset], 
								buffer_length - sp->write_out_offset);
		if (sp->write_out_count != buffer_length - sp->write_out_offset){
			printk("%s: Didn't send all the data out! length of write == %d, length written = %d\n", 
						__func__, 
						buffer_length - sp->write_out_offset, 
						sp->write_out_count);
		}
		else {
			printk("%s: Sent all the rest of the data\n", __func__);

			//need to see if there is more data to encode

		}
	}
	else {
		//finished sending data to the FPGA give the bus a callback
		sp_sb_write_callback(&sp->sb);
	}
}

/**
 * sp_write_callback
 * Description: called when a write has been completed
 *	if there is a long write, then this is used to send the rest of 
 *	the rest of the data
 *
 * Return:
 *	Nothing
 **/
void sp_write_callback(sycamore_protocol_t *sp, u32 bytes_left){
	printk("%s: entered\n", __func__);
	sp->hw_bytes_left = bytes_left;
	if (sp->hw_bytes_left > 0){
		printk("%s: usb-serial didn't send all bytes to the FPGA there are %d bytes left\n", __func__, bytes_left);
	}

	//if this is not equal to zero, then resubmit
	//crap this could be the initial data packet!	
//XXX: just assume that all the data was sent for now, I need to see if there was an error in the status

/*
	by now the encoded buffer should be ready
	I can probably send the data down in here, and process the next bach of encoded data in the write_work,
	but for this first version I'll put everything in the write_work, and save that optimization for later
*/
	schedule_work(&sp->write_work);
}

/**
 * sp_read_data
 * Description: reads the data from the low level driver
 *	some drivers send data in a 'peice meal' fashion so
 *	this function will accept all or part of the data received
 *	and put it together for the higher level functions

 *
 * Return:
 *	Nothing
 */
void sp_hardware_read(		
						sycamore_protocol_t *sp, 
						char *buffer, 
						int length){
	int i = 0;
	int ch = 0;
	int read_buffer_pos = 0; 
	printk("%s: entered\n", __func__);
//XXX: I forgot why I needed to do '++i'
	for (i = 0; i < length; ++i){
		ch = buffer[i];
		if (ch == 'S'){
			printk("%s: Found S\n", __func__);
			//reset all variables
			sp->read_command		=	0;
			sp->read_size			=	0;
			sp->read_data			=	0;
			sp->read_data_count		=	0;
			sp->read_data_pos		=	0;
			sp->read_address		=	0;
			sp->read_device_address	=	0;
			sp->read_pos			=	0;
			sp->read_state			=	READ_SIZE;
			continue;
		}
		//read state machine
		switch (sp->read_state){
			case (READ_IDLE):
				//waiting for an 'S'
				continue;
				break;
			case (READ_SIZE):
				/* 
					next seven bytes is the nubmer of bytes to read
					not including the first 32 bit dword
				*/

				if (ch >= 'A'){
					//take care of the hex values greater than 9
					ch -= ('A' - 10); //compiler optimize this please
				}
				else {
					ch -= '0';
				}
				sp->read_pos++;
				sp->read_size += ch;

				//transition condition
				if (sp->read_pos == 7){
					
					//setup the read data count to at least read the first
					//32 bit word
					sp->read_data_count = sp->read_size + 1;
					sp->read_state = READ_COMMAND;
					sp->read_pos = 0;
					printk ("%s: read size = %d\n", __func__, sp->read_size);
				}
				else {
					//shift the data up by four
					sp->read_size = sp->read_size << 4;
				}
				break;
			case (READ_COMMAND):
				if (ch >= 'A'){
					//take care of the hex values greater than 9
					ch -= ('A' - 10); //compiler optimize this please
				}
				else {
					ch -= '0';
				}
				sp->read_command += ch;	
				sp->read_pos++;
				//transition condition

				if (sp->read_pos == 8){
					 sp->read_command = ~(sp->read_command);
					 switch (sp->read_command){
					 	case (SYCAMORE_PING): 
							printk("%s: Received a ping response\n", __func__);
							break;
						case (SYCAMORE_WRITE):
							printk("%s: Received a write ack\n", __func__);
							break;
						case (SYCAMORE_READ):
							printk("%s: Received a read response\n", __func__);
							break;
						case (~SYCAMORE_INTERRUPTS):
							//this is the only command that isn't inverted
							printk("%s: Received an interrupt\n", __func__);
							sp->read_command = ~(sp->read_command);
							//respond to interrupts
							break;
						default:
							printk("%s: Received an illegal command!, resetting state machine: %8X\n", __func__, sp->read_command);
							sp->read_state = READ_IDLE;
							continue;
							break;
					 }
					/*
					   if the command was read we will need
					   to read all the data back
					 */

					sp->read_pos	=	0;
					sp->read_state = READ_ADDRESS;
				}
				else {
					sp->read_command = sp->read_command << 4;
				}
				break;
			case (READ_ADDRESS):
				/*
				   the next eight bytes is the address
				 */
				/*
				   if the address top two bytes == 0
				   then this is a control packet
				   if the address top two bytes == FF
				   then this is interrupts
				 */
				if (ch >= 'A'){
					//take care of the hex values greater than 9
					ch -= ('A' - 10); //compiler optimize this please
				}
				else {
					ch -= '0';
				}
				sp->read_address += ch;	
				sp->read_pos++;

				//transition condition
				if (sp->read_pos == 8) {
					sp->read_device_address = (sp->read_address & 0xFF000000) >> 24;
					sp->read_address = (sp->read_address & 0x00FFFFFF);
					sp->read_state = READ_DATA;
					sp->read_pos = 0;
					sp->read_data = 0;
				}
				else {
					sp->read_address = sp->read_address << 4;
				}
				break;
			case (READ_DATA):
				/*
				   if the command was a read then we 
				   need to possibly count the data in
				   the first 8 bytes are always there
				 */
	
				if (ch >= 'A'){
					//take care of the hex values greater than 9
					ch -= ('A' - 10); //compiler optimize this please
				}
				else {
					ch -= '0';
				}
				sp->read_data += ch;	
				sp->read_pos++;
				if (sp->read_pos == 8){

					sp->read_data_count--;
					sp->read_out_data[0] = ((u8) sp->read_data >> 24);
					sp->read_out_data[1] = ((u8) sp->read_data >> 16);
					sp->read_out_data[2] = ((u8) sp->read_data >> 8);
					sp->read_out_data[3] = ((u8) sp->read_data);
					//send data up to the bus one double word at a time
					sp_sb_read(	&sp->sb,
								sp->read_command,
								sp->read_device_address,
								sp->read_address,
								sp->read_data_pos,
								sp->read_size + 1,
								READ_BUF_SIZE,
								sp->read_data_count,
								&sp->read_out_data[0]);
							/*
							the position is defined in terms of 4 * 8 = 32
							and were copying it into a byte array
							*/
					read_buffer_pos = sp->read_data_pos << 2;
/*
					if (sp->read_data_count == 0){
//XXX: tell the sycamore bus we are done with a read
//						dev->read_address = sp->read_address;
//						dev->read_address = sp->read_size + 1;
					}
*/
					if (sp->read_data_count == 0){
						sp->read_state = READ_IDLE;
						printk("%s: parsed data\n", __func__);
						printk("c:%8X\n", 
										sp->read_command);
						printk("a:%8X : %6X\n", 
										sp->read_device_address, 
										sp->read_address);
						printk("s:%8d\n", 
										sp->read_size + 1);
						printk("d:%.8X\n\n", 
										sp->read_data);

					}
					else {
						sp->read_pos = 0;
						sp->read_data = 0;
						sp->read_data_pos++;
					}
				}
				else {
					//shift everything up a nibble
					sp->read_data = sp->read_data << 4;
				}
				break;
			default:
				/*
				   how did we get here?
				   something went wrong
				 */
				sp->read_state = READ_IDLE;
				printk("%s: Entered Illegal state in read state machine", __func__);
				break;
		}
	}
}


int sb_sp_write(
		sycamore_bus_t *sb,
		u32 command,
		u8 device_address,
		u32 offset,
		u8 * out_buffer,
		u32 length){

	sycamore_protocol_t *sp = NULL;
	int retval = 0;
	int length_aligned = 0;

	printk("%s: entered\n", __func__);
	sp = container_of(sb, sycamore_protocol_t, sb); 

	//setup the internal write buffer to point to the output buffer
	sp->write_command = command;
	sp->write_buffer = out_buffer;
	sp->write_buffer_size = length;
	sp->write_out_offset = 0;

	//it might be a good idea to zero out the encoded buffer
	retval = hardware_write (
				sp,
				command,
				device_address,
				offset,
				out_buffer,
				length / 4);


	//start by using the front buffer
	sp->current_buffer = 0;
	//the front buffer is begin used to transmit the command
	sp->encoded_buffer[1].encoded_buf_size = 0;
	encode_buffer(sp, 1);
	
	return retval;
}

/**
 * hardware write
 * Description: write raw bytes to the hardware driver
 *
 * Return:
 *	number of bytes written
 *	-1 if there is no hardware write function setup
 **/
int hardware_write (
				sycamore_protocol_t * sp,
				u32 command,
				u8 device_address,
				u32 offset,
				char * buffer,
				u32 length){
	u32 true_data_size = 0;

	u32 buffer_size = 0;
	u8 * buffer = NULL;

	buffer = &sp->encoded_buffer[0].encoded_buffer[0];
	
	if (length > 0){
		true_data_size = length - 1;
	}

	//use the first encoded buffer to write the data out

	//for reading command and the case where data doesn't matter
	if ((length == 0) || ((0xFFFF & command) == SYCAMORE_READ)){
		buffer_size = snprintf(
						buffer, 
						ENCODED_BUF_SIZE, 
						"L%07X%08X%02X%06X%s",
						true_data_size,
						command,
						device_address,
						offset,
						"00000000");
	}
	else {
		buffer_size = snprintf (
						buffer, 
						&sp->write_buffer[0], 
						ENCODED_BUF_SIZE, 
						"L%07X%08X%02X%06X", 
						true_data_size, 
						command, 
						device_address, 
						offset);
	}

	buffer[buffer_size] = 0;
	printk ("%s: length = %d, sending: %s\n", 
			__func__, 
			buffer_size, 
			buffer);


	sp->encoded_buffer[0].encoded_buffer_size = buffer_size;
	if (sp->write_func != NULL){
		sp->write_out_count = sp->write_func(
								sp->write_data, 
								buffer, 
								buffer_size);

		if (sp->write_out_count != sp->write_out_size){
			printk("%s: Didn't send all the data out! length of write == %d, length written = %d\n", 
				__func__, 
				buffer_size, 
				sp->write_out_count);
		}
		else {
			printk("%s: Sent all data at once!\n", __func__);
		}
		return sp->write_out_size;
	}

	//write function is not defined
	return -1;
}


/**
 * encode_buffer
 * Description: this encodes data to the uart protocol
 *	this reads the write_buffer and generates an ascii version
 *	of the data, so all the bytes of data take two bytes in the encoded version
 *	this will be called after the first part of the transmission to the FPGA
 *	while the usb-serial is processing it, and after any consecutive writes
 *
 * Return:
 *	the lengths of bytes encoded from the ORIGINAL BUFFER
 **/
int encode_buffer(sycamort_protocol_t *sp, int buffer_select){
	int i = 0;
	int buffer_index = 0;
	int length_to_process = 0;
	u8 top_nibble;
	u8 bottom_nibble;
	printk("%s: entered\n", __func__);

	//all output data must be a multiple of four because we send 32 bits down at a time, so if the data is less than that we
	// buffer it
	if (sp->out_size == 0){
		return;
	}

	//get the number of bytes that I still need to process from the write buffer
	length_to_process = sp->write_out_size - sp->write_out_offset;

	//check if I have enough room in the buffer to do this?
	if (length_to_process > ENCODED_BUF_SIZE / 2){
		//not enough room so this won't finish the write transaction
		length_to_process = ENCODED_BUF_SIZE / 2;	
	}

	for (i = 0; i < length_to_process; i++ ){
		buffer_index = i * 2;
		
		top_nibble = sp->write_buffer[i] >> 4;
		bottom_nibble = sp->write_buffer[i] 0xF;

		if (top_nibble > 0x0A){
			top_nibble += ('A' - 10);
		}
		else {
			top_nibble += '0';
		}
		
		if (bottom_nibble > 0x0A){
			bottom_nibble += ('A' - 10);
		}
		else {
			bottom_nibble += '0';
		}

		sp->encoded_buffer[buffer_select].encoded_buffer[buffer_index] = top_nibble;
		sp->encoded_buffer[buffer_select].encoded_buffer[buffer_index + 1] = bottom_nibble;
	}

	sp->encoded_buffer[buffer_select].encoded_buf_size = length_to_process;
	return length_to_process;
}