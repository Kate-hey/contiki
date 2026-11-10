/*
 * Copyright (c) 2007, Swedish Institute of Computer Science.
 * All rights reserved. 
 *
 * Redistribution and use in source and binary forms, with or without 
 * modification, are permitted provided that the following conditions 
 * are met: 
 * 1. Redistributions of source code must retain the above copyright 
 *    notice, this list of conditions and the following disclaimer. 
 * 2. Redistributions in binary form must reproduce the above copyright 
 *    notice, this list of conditions and the following disclaimer in the 
 *    documentation and/or other materials provided with the distribution. 
 * 3. Neither the name of the Institute nor the names of its contributors 
 *    may be used to endorse or promote products derived from this software 
 *    without specific prior written permission. 
 *
 * THIS SOFTWARE IS PROVIDED BY THE INSTITUTE AND CONTRIBUTORS ``AS IS'' AND 
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE INSTITUTE OR CONTRIBUTORS BE LIABLE 
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL 
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS 
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT 
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY 
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF 
 * SUCH DAMAGE. 
 *
 * This file is part of the Contiki operating system.
 * 
 * Author: Oliver Schmidt <ol.sc@web.de>
 *
 */

#include <apple2.h>

#include "contiki.h"

/* The enhanced Apple//e doesn't have a hardware clock whatsoever. Therefore the
 * cc65 C-library for this target doesn't include an implementation of clock().
 */

enum {
  TICK_LOOP,
  TICK_VBL_EDGE,
  TICK_VERTCNT
};

static unsigned char tick_source;
static unsigned char prev;
static unsigned char frames;
static clock_time_t time;

/*-----------------------------------------------------------------------------------*/
static void
count_frame(void)
{
  if(++frames == 15) {
    frames = 0;
    ++time;
  }
}
/*-----------------------------------------------------------------------------------*/
void
clock_init(void)
{
  unsigned char type = get_ostype();

  if(type >= APPLE_IIGS) {
    tick_source = TICK_VERTCNT;
  } else if(type < APPLE_IIC || type > APPLE_IICPLUS) {
    tick_source = TICK_VBL_EDGE;
  }
}
/*-----------------------------------------------------------------------------------*/
void
clock_update(void)
{
  static unsigned int count;
  unsigned char sample;

  switch(tick_source) {
  case TICK_VERTCNT:
    /* The IIgs VBL-high phase is too short to sample reliably, the line
     * counter wraps once per frame and can't be missed. */
    sample = *(unsigned char *)0xC02E;
    if(sample < prev) {
      count_frame();
    }
    prev = sample;
    break;

  case TICK_VBL_EDGE:
    /* RDVBL bit 7 is 1 outside blanking, so the low-to-high edge comes once
     * per frame. */
    sample = *(unsigned char *)0xC019 & 0x80;
    if(sample && !prev) {
      count_frame();
    }
    prev = sample;
    break;

  default:
    count += 14;
    if(count > 1000) {
      count = 0;
      ++time;
    }
    break;
  }
}
/*-----------------------------------------------------------------------------------*/
clock_time_t
clock_time(void)
{
  return time;
}
/*-----------------------------------------------------------------------------------*/
unsigned long
clock_seconds(void)
{
  return time / CLOCK_CONF_SECOND;
}
/*-----------------------------------------------------------------------------------*/
