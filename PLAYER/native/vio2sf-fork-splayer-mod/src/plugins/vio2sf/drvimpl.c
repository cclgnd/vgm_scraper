#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

// #include "desmume/MMU.h"
// #include "desmume/armcpu.h"
// #include "desmume/ndssystem.h"
// #include "desmume/spu_exports.h"
// #include "desmume/cp15.h"
#include "desmume/state.h"

#include "zlib/zlib.h"
#include "../xsfc/tagget.h"
#include "../xsfc/drvimpl.h"

volatile BOOL execute = FALSE;

static struct
{
	unsigned char *rom;
	unsigned char *state;
	unsigned romsize;
	unsigned statesize;
	unsigned stateptr;
} loaderwork = { 0, 0, 0, 0, 0 };

static void load_term(void)
{
	if (loaderwork.rom)
	{
		free(loaderwork.rom);
		loaderwork.rom = 0;
	}
	loaderwork.romsize = 0;
	if (loaderwork.state)
	{
		free(loaderwork.state);
		loaderwork.state = 0;
	}
	loaderwork.statesize = 0;
}

static int load_map(int issave, unsigned char *udata, unsigned usize)
{	
	unsigned char *iptr;
	unsigned isize;
	unsigned char *xptr;
	unsigned xsize = getdwordle(udata + 4);
	unsigned xofs = getdwordle(udata + 0);
	if (issave)
	{
		iptr = loaderwork.state;
		isize = loaderwork.statesize;
		loaderwork.state = 0;
		loaderwork.statesize = 0;
	}
	else
	{
		iptr = loaderwork.rom;
		isize = loaderwork.romsize;
		loaderwork.rom = 0;
		loaderwork.romsize = 0;
	}
	if (!iptr)
	{
		unsigned rsize = xofs + xsize;
		if (!issave)
		{
			rsize -= 1;
			rsize |= rsize >> 1;
			rsize |= rsize >> 2;
			rsize |= rsize >> 4;
			rsize |= rsize >> 8;
			rsize |= rsize >> 16;
			rsize += 1;
		}
		iptr = malloc(rsize + 10);
		if (!iptr)
			return XSF_FALSE;
		memset(iptr, 0, rsize + 10);
		isize = rsize;
	}
	else if (isize < xofs + xsize)
	{
		unsigned rsize = xofs + xsize;
		if (!issave)
		{
			rsize -= 1;
			rsize |= rsize >> 1;
			rsize |= rsize >> 2;
			rsize |= rsize >> 4;
			rsize |= rsize >> 8;
			rsize |= rsize >> 16;
			rsize += 1;
		}
		xptr = realloc(iptr, xofs + rsize + 10);
		if (!xptr)
		{
			free(iptr);
			return XSF_FALSE;
		}
		iptr = xptr;
		isize = rsize;
	}
	memcpy(iptr + xofs, udata + 8, xsize);
	if (issave)
	{
		loaderwork.state = iptr;
		loaderwork.statesize = isize;
	}
	else
	{
		loaderwork.rom = iptr;
		loaderwork.romsize = isize;
	}
	return XSF_TRUE;
}

static int load_mapz(int issave, unsigned char *zdata, unsigned zsize, unsigned zcrc)
{
	int ret;
	int zerr;
	uLongf usize = 8;
	uLongf rsize = usize;
	unsigned char *udata;
	unsigned char *rdata;

	udata = malloc(usize);
	if (!udata)
		return XSF_FALSE;

	while (Z_OK != (zerr = uncompress(udata, &usize, zdata, zsize)))
	{
		if (Z_MEM_ERROR != zerr && Z_BUF_ERROR != zerr)
		{
			free(udata);
			return XSF_FALSE;
		}
		if (usize >= 8)
		{
			usize = getdwordle(udata + 4) + 8;
			if (usize < rsize)
			{
				rsize += rsize;
				usize = rsize;
			}
			else
				rsize = usize;
		}
		else
		{
			rsize += rsize;
			usize = rsize;
		}
		free(udata);
		udata = malloc(usize);
		if (!udata)
			return XSF_FALSE;
	}

	rdata = realloc(udata, usize);
	if (!rdata)
	{
		free(udata);
		return XSF_FALSE;
	}

	if (0)
	{
		unsigned ccrc = crc32(crc32(0L, Z_NULL, 0), rdata, usize);
		if (ccrc != zcrc)
			return XSF_FALSE;
	}

	ret = load_map(issave, rdata, usize);
	free(rdata);
	return ret;
}

static int load_psf_one(unsigned char *pfile, unsigned bytes)
{
	unsigned char *ptr = pfile;
	unsigned code_size;
	unsigned resv_size;
	unsigned code_crc;
	if (bytes < 16 || getdwordle(ptr) != 0x24465350)
		return XSF_FALSE;

	resv_size = getdwordle(ptr + 4);
	code_size = getdwordle(ptr + 8);
	code_crc = getdwordle(ptr + 12);

	if (resv_size)
	{
		unsigned resv_pos = 0;
		ptr = pfile + 16;
		if (16+ resv_size > bytes)
			return XSF_FALSE;
		while (resv_pos + 12 < resv_size)
		{
			unsigned save_size = getdwordle(ptr + resv_pos + 4);
			unsigned save_crc = getdwordle(ptr + resv_pos + 8);
			if (getdwordle(ptr + resv_pos + 0) == 0x45564153)
			{
				if (resv_pos + 12 + save_size > resv_size)
					return XSF_FALSE;
				if (!load_mapz(1, ptr + resv_pos + 12, save_size, save_crc))
					return XSF_FALSE;
			}
			resv_pos += 12 + save_size;
		}
	}

	if (code_size)
	{
		ptr = pfile + 16 + resv_size;
		if (16 + resv_size + code_size > bytes)
			return XSF_FALSE;
		if (!load_mapz(0, ptr, code_size, code_crc))
			return XSF_FALSE;
	}

	return XSF_TRUE;
}

typedef struct
{
	const char *tag;
	int taglen;
	int level;
	int found;
} loadlibwork_t;

static int load_psf_and_libs(int level, void *pfile, unsigned bytes);

static int load_psfcb(void *pWork, const char *pNameTop, const char *pNameEnd, const char *pValueTop, const char *pValueEnd)
{
	loadlibwork_t *pwork = (loadlibwork_t *)pWork;
	int ret = xsf_tagenum_callback_returnvaluecontinue;
	if (pNameEnd - pNameTop == pwork->taglen && !_strnicmp(pNameTop, pwork->tag , pwork->taglen))
	{
		unsigned l = pValueEnd - pValueTop;
		char *lib = malloc(l + 1);
		if (!lib)
		{
			ret = xsf_tagenum_callback_returnvaluebreak;
		}
		else
		{
			void *libbuf;
			unsigned libsize;
			memcpy(lib, pValueTop, l);
			lib[l] = '\0';
			if (!xsf_get_lib(lib, &libbuf, &libsize))
			{
				ret = xsf_tagenum_callback_returnvaluebreak;
			}
			else
			{
				if (!load_psf_and_libs(pwork->level + 1, libbuf, libsize))
					ret = xsf_tagenum_callback_returnvaluebreak;
				else
					pwork->found++;
				free(libbuf);
			}
			free(lib);
		}
	}
	return ret;
}

static int load_psf_and_libs(int level, void *pfile, unsigned bytes)
{
	int haslib = 0;
	loadlibwork_t work;

	work.level = level;
	work.tag = "_lib";
	work.taglen = strlen(work.tag);
	work.found = 0;

	if (level <= 10 && xsf_tagenum(load_psfcb, &work, pfile, bytes) < 0)
		return XSF_FALSE;

	haslib = work.found;

	if (!load_psf_one(pfile, bytes))
		return XSF_FALSE;

/*	if (haslib) */
	{
		int n = 2;
		do
		{
			char tbuf[16];
#ifdef HAVE_SPRINTF_S
			sprintf_s(tbuf, sizeof(tbuf), "_lib%d", n++);
#else
			sprintf(tbuf, "_lib%d", n++);
#endif
			work.tag = tbuf;
			work.taglen = strlen(work.tag);
			work.found = 0;
			if (xsf_tagenum(load_psfcb, &work, pfile, bytes) < 0)
				return XSF_FALSE;
		}
		while (work.found);
	}
	return XSF_TRUE;
}

static int load_psf(void *pfile, unsigned bytes)
{
	load_term();

	return load_psf_and_libs(1, pfile, bytes);
}

static void load_getstateinit(unsigned ptr)
{
	loaderwork.stateptr = ptr;
}


static struct
{
	u32 cycles;
	int xfs_load;
	int sync_type;
	int arm7_clockdown_level;
	int arm9_clockdown_level;
	NDS_state * core;
} sndifwork = { 0, 0, 0, 0, 0, 0,};

static struct armcpu_ctrl_iface *arm9_ctrl_iface = 0;
static struct armcpu_ctrl_iface *arm7_ctrl_iface = 0;

int xsf_start(void *pfile, unsigned bytes)
{
	int frames = xsf_tagget_int("_frames", pfile, bytes, -1);
	int clockdown = xsf_tagget_int("_clockdown", pfile, bytes, 0);
	sndifwork.sync_type = xsf_tagget_int("_vio2sf_sync_type", pfile, bytes, 0);
	sndifwork.arm9_clockdown_level = xsf_tagget_int("_vio2sf_arm9_clockdown_level", pfile, bytes, clockdown);
	sndifwork.arm7_clockdown_level = xsf_tagget_int("_vio2sf_arm7_clockdown_level", pfile, bytes, clockdown);

	NDS_state * core = ( NDS_state * ) calloc(1, sizeof(NDS_state));
	sndifwork.core = core;

	sndifwork.xfs_load = 0;
	if (!load_psf(pfile, bytes))
		return XSF_FALSE;

	if ( state_init(core) )
	{
		state_deinit(core);
		return XSF_FALSE;
	}

	core->dwInterpolation = 0;
	core->dwChannelMute = 0;
	
	if (!sndifwork.arm7_clockdown_level)
		sndifwork.arm7_clockdown_level = clockdown;
	if (!sndifwork.arm9_clockdown_level)
		sndifwork.arm9_clockdown_level = clockdown;

	core->initial_frames = frames;
	core->sync_type = sndifwork.sync_type;
	core->arm7_clockdown_level = sndifwork.arm7_clockdown_level;
	core->arm9_clockdown_level = sndifwork.arm9_clockdown_level;
        
	execute = FALSE;

	if ( loaderwork.rom )
		state_setrom( core, loaderwork.rom, (u32) loaderwork.romsize, 1 );
	
	state_loadstate(core, loaderwork.state, (u32) loaderwork.statesize );
	
	if (loaderwork.state) {
		free(loaderwork.state);
		loaderwork.state = 0;
	}

	execute = TRUE;
	sndifwork.xfs_load = 1;

	
	return XSF_TRUE;
}

void dlog( const char *format, ... )
{
	va_list ap;
	static char buf[1024];

	va_start( ap, format );
	int ret=vsnprintf(buf, sizeof(buf), format, ap );
	va_end( ap );
	if(ret>=0){
		OutputDebugString(buf);

		DWORD dwAB;
		WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), buf, ret, &dwAB, NULL);
	}
}

int xsf_gen(void *pbuffer, unsigned samples)
{
	if (!sndifwork.xfs_load) return 0;
	// dlog("%s: sample=%d\n", __func__,samples);
	state_render(sndifwork.core, pbuffer, samples);
	return samples;
}

void xsf_term(void)
{
	if (sndifwork.core){
		state_deinit(sndifwork.core);
		sndifwork.xfs_load = 0;
		sndifwork.core = NULL;
	}
	load_term();
}

struct SPU_struct *hack_GetSpuCore(void){
	if (!sndifwork.xfs_load || !sndifwork.core) return NULL;
	return sndifwork.core->SPU_core;
}