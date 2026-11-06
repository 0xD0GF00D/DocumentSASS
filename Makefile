CC = cc
NVCC = /usr/local/cuda/bin/nvcc
NVDISASM = /usr/local/cuda/bin/nvdisasm
PYTHON = python3

architectures := $(shell $(NVCC) --help | grep -oE '\bsm_[0-9]+[a-z]?' | sort -u)

targets = $(architectures:=_instructions.txt) $(architectures:=_latencies.txt)

all: $(targets)

clean:
	-rm -f $(targets) *.cubin *.bin *_state.txt *.raw *.done intercept.so

%.so: %.c
	$(CC) -fPIC -shared -o $@ $< -ldl

%.cubin: example.cu
	$(NVCC) -o $@ -arch=$* -cubin $<

# $* evaluates strictly to the architecture name (e.g., sm_75)
%.done: %.cubin intercept.so
	@OMP_NUM_THREADS=1 \
	DUMP_PAYLOAD_PATH=$*.bin \
	DUMP_STATE_PATH=$*_state.txt \
	LD_PRELOAD=./intercept.so $(NVDISASM) $< > $*.raw 2>/dev/null || true
	@if [ ! -s $*.raw ] && [ ! -f $*.bin ]; then \
		echo "[$*] Hook unneeded or incompatible. Running native fallback..."; \
		$(NVDISASM) $< > $*.raw 2>/dev/null; \
	fi
	@touch $@

%_instructions.txt %_latencies.txt: %.done
	$(PYTHON) funnel.py $* $(NVDISASM)
