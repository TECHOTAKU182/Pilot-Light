/* SL25 Rev B - CH552G minimal WS2812B-V5 test firmware
 * Build with SDCC and the CH552 device headers from WCH CH55X EVT.
 * LED data: U1 pin 3 = P1.5, through R3 (330 ohm).
 * This intentionally has no USB application protocol: it cycles colors
 * so the assembled hardware can be verified before a host-control firmware.
 */
#include <stdint.h>

typedef unsigned char u8;
typedef unsigned int  u16;

__sfr __at (0x90) P1;
__sfr __at (0x91) P1M1;
__sfr __at (0x92) P1M0;
__sbit __at (0x95) LED_DATA;       /* P1.5 */
__sbit __at (0xAF) EA;              /* IE.7, global interrupt enable */

static void delay_ms(u16 ms)
{
    u16 i;
    while (ms--) {
        for (i = 0; i < 240; ++i) {
            __asm nop __endasm;
        }
    }
}

/* Approximate 800 kHz WS2812 waveform at the CH552 24 MHz internal clock.
 * Keep this routine in code memory and do not enable interrupts while sending.
 */
static void ws_bit(u8 one)
{
    LED_DATA = 1;
    if (one) {
        __asm nop; nop; nop; nop; nop; nop; nop; nop; nop; nop; __endasm;
        LED_DATA = 0;
        __asm nop; nop; nop; nop; __endasm;
    } else {
        __asm nop; nop; nop; __endasm;
        LED_DATA = 0;
        __asm nop; nop; nop; nop; nop; nop; nop; nop; nop; nop; __endasm;
    }
}

static void ws_byte(u8 v)
{
    u8 b;
    for (b = 0x80; b; b >>= 1) ws_bit((v & b) != 0);
}

static void ws_color(u8 r, u8 g, u8 b)
{
    /* WS2812B expects GRB, MSB first. */
    EA = 0;
    ws_byte(g); ws_byte(r); ws_byte(b);
    LED_DATA = 0;
    EA = 1;
    delay_ms(1);                    /* reset low >280 us */
}

void main(void)
{
    P1M1 &= ~(1 << 5);              /* push-pull output */
    P1M0 |=  (1 << 5);
    LED_DATA = 0;
    while (1) {
        ws_color(255, 0, 0);        /* red */
        delay_ms(700);
        ws_color(0, 255, 0);        /* green */
        delay_ms(700);
        ws_color(0, 0, 255);        /* blue */
        delay_ms(700);
        ws_color(255, 180, 0);       /* yellow */
        delay_ms(700);
    }
}
