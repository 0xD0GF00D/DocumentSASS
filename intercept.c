#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <string.h>
#include <sys/mman.h>

#define STOLEN_LEN 13

static const uint8_t SIG[STOLEN_LEN] = {
    0x85, 0xD2, 0x8B, 0x4F, 0x04, 0x44, 0x8B, 0x47, 0x08, 0x0F, 0xB6, 0x47, 0x0C
};

static void *trampoline = NULL;
static int payload_count = 0;
typedef char (*decrypt_fn)(uint32_t *state, char *buffer, size_t length);

char hook_func(uint32_t *state, char *buffer, size_t length) {
    decrypt_fn real_decrypt = (decrypt_fn)trampoline;
    char ret = real_decrypt(state, buffer, length);

    // Capture buffers >= 500 bytes (catches smaller latency slices)
    if (length >= 500) {
        const char *prefix = getenv("DUMP_PAYLOAD_PREFIX");
        if (prefix && buffer) {
            char path[512];
            payload_count++;
            snprintf(path, sizeof(path), "%s_payload_%d.bin", prefix, payload_count);

            FILE *fp = fopen(path, "wb");
            if (fp) {
                fwrite(buffer, 1, length, fp);
                fclose(fp);
            }

            // Print first 40 chars of decrypted buffer to stderr for diagnostics
            char sample[41];
            size_t sample_len = length < 40 ? length : 40;
            for (size_t i = 0; i < sample_len; i++) {
                sample[i] = (buffer[i] >= 32 && buffer[i] <= 126) ? buffer[i] : '.';
            }
            sample[sample_len] = '\0';
            fprintf(stderr, "[HOOK] Payload #%d: %zu bytes | Sample: %s\n", payload_count, length, sample);
        }
    }

    return ret;
}

static void *find_decrypt_isa(void) {
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return NULL;

    char line[512];
    uintptr_t start, end;
    char perms[5];
    void *found = NULL;

    while (fgets(line, sizeof(line), maps)) {
        if (!strstr(line, "nvdisasm")) continue;
        if (sscanf(line, "%lx-%lx %4s", &start, &end, perms) != 3) continue;

        if (perms[2] == 'x') {
            uint8_t *ptr = (uint8_t *)start;
            size_t len = end - start;
            for (size_t i = 0; i + STOLEN_LEN <= len; i++) {
                if (memcmp(ptr + i, SIG, STOLEN_LEN) == 0) {
                    found = (void *)(ptr + i);
                    break;
                }
            }
        }
        if (found) break;
    }
    fclose(maps);
    return found;
}

__attribute__((constructor))
static void install_hooks(void) {
    void *decrypt_target = find_decrypt_isa();
    if (!decrypt_target) return;

    uintptr_t page_size = sysconf(_SC_PAGE_SIZE);
    uintptr_t page_start = (uintptr_t)decrypt_target & ~(page_size - 1);
    mprotect((void *)page_start, page_size * 2, PROT_READ | PROT_WRITE | PROT_EXEC);

    trampoline = mmap(NULL, page_size, PROT_READ | PROT_WRITE | PROT_EXEC,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);

    memcpy(trampoline, decrypt_target, STOLEN_LEN);

    uint8_t jmp_back[13] = {
        0x49, 0xBB, 0, 0, 0, 0, 0, 0, 0, 0,
        0x41, 0xFF, 0xE3
    };
    *(uintptr_t *)(&jmp_back[2]) = (uintptr_t)decrypt_target + STOLEN_LEN;
    memcpy((uint8_t *)trampoline + STOLEN_LEN, jmp_back, 13);

    uint8_t jmp_hook[13] = {
        0x49, 0xBB, 0, 0, 0, 0, 0, 0, 0, 0,
        0x41, 0xFF, 0xE3
    };
    *(uintptr_t *)(&jmp_hook[2]) = (uintptr_t)&hook_func;
    memcpy(decrypt_target, jmp_hook, 13);
}
