CC = cc
NVCC = /usr/local/cuda/bin/nvcc
NVDISASM = /usr/local/cuda/bin/nvdisasm
PYTHON = python3

architectures := $(shell $(NVCC) --help | grep -oE '\bsm_[0-9]+[a-z]?' | sort -u)

targets = $(architectures:=_instructions.txt) $(architectures:=_latencies.txt)

all: $(targets)

clean:
	-rm -f $(targets) *.cubin *_payload_*.bin *.done intercept.so

%.so: %.c
	$(CC) -fPIC -shared -o $@ $< -ldl

%.cubin: example.cu
	$(NVCC) -o $@ -arch=$* -cubin $<

%.done: %.cubin intercept.so
	@OMP_NUM_THREADS=1 \
	DUMP_PAYLOAD_PREFIX=$* \
	LD_PRELOAD=./intercept.so $(NVDISASM) $< > /dev/null 2>&1 || true
	@touch $@

%_instructions.txt %_latencies.txt: %.done
	$(PYTHON) funnel.py $*
