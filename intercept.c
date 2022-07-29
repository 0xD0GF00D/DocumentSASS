#define _GNU_SOURCE
#include <stdio.h>
#include <dlfcn.h>
#include <unistd.h>
#include <string.h>

// https://stackoverflow.com/a/18351147
__attribute__ ((__noinline__))
void * get_pc1 () { return __builtin_extract_return_addr(__builtin_return_address(1)); }

__attribute__ ((__noinline__))
void * get_fa1 () { return __builtin_frame_address (1); }


void * memcpy(void * __restrict dest, const void * __restrict src, size_t num) {
    // https://www.thegeekstuff.com/2012/03/reverse-engineering-tools/
    
    // https://osterlund.xyz/posts/2018-03-12-interceptiong-functions-c.html
    void * (*lmemcpy)(void * __restrict, const void * __restrict, size_t) = dlsym(RTLD_NEXT, "memcpy");
    
    // https://stackoverflow.com/a/18351147
    //printf("\n<%p>\n", get_pc1());
    //printf("\n<%p>\n", get_fa1());
    printf("\n<%p %p %zu>\n", dest, src, num);
    // https://stackoverflow.com/a/1716621
    fflush(stdout); // Will now print everything in the stdout buffer
    
    // https://stackoverflow.com/a/15660266
    fwrite(src, sizeof(char), num, stdout);
    fflush(stdout); // Will now print everything in the stdout buffer
    
    return lmemcpy(dest, src, num);
}