#include <stdint.h>

struct CycleAbiHeader {
    uint32_t abi_version;
    uint32_t info_size;
};

static const struct CycleAbiHeader ABI = {1, sizeof(struct CycleAbiHeader)};

const struct CycleAbiHeader* rustdv_cycle_abi_info(void) { return &ABI; }
void* rustdv_cycle_create(void* outputs) { return outputs; }
uint32_t rustdv_cycle_step(void* context, const void* inputs, void* outputs) {
    (void)context;
    (void)inputs;
    (void)outputs;
    return 2;
}
uint32_t rustdv_cycle_finish(void* context) {
    (void)context;
    return 2;
}
const char* rustdv_cycle_last_error(void* context) {
    (void)context;
    return "fixture should be rejected before model creation";
}
void rustdv_cycle_destroy(void* context) { (void)context; }
