obj-m += mntracer.o
CFLAGS_mntracer.o := -I$(src)

all:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
