cmake_minimum_required(VERSION 3.5)

set(TARGET_NAME vio2sf)
project(${TARGET_NAME} LANGUAGES C CXX)

set(BASE_DIR ${CMAKE_CURRENT_SOURCE_DIR})

set(EXTRA_SOURCES)
set(COMPILE_OPTIONS)
set(LINK_OPTIONS)
set(LIBS)

set(SOURCES
	${BASE_DIR}/src/plugins/vio2sf/drvimpl.c
	${BASE_DIR}/src/vio2sf/desmume/armcpu.c
	${BASE_DIR}/src/vio2sf/desmume/arm_instructions.c
	${BASE_DIR}/src/vio2sf/desmume/barray.c
	${BASE_DIR}/src/vio2sf/desmume/bios.c
	${BASE_DIR}/src/vio2sf/desmume/cp15.c
	${BASE_DIR}/src/vio2sf/desmume/FIFO.c
	${BASE_DIR}/src/vio2sf/desmume/GPU.c
	${BASE_DIR}/src/vio2sf/desmume/isqrt.c
	${BASE_DIR}/src/vio2sf/desmume/matrix.c
	${BASE_DIR}/src/vio2sf/desmume/mc.c
	${BASE_DIR}/src/vio2sf/desmume/MMU.c
	${BASE_DIR}/src/vio2sf/desmume/NDSSystem.c
	${BASE_DIR}/src/vio2sf/desmume/resampler.c
	${BASE_DIR}/src/vio2sf/desmume/state.c
	${BASE_DIR}/src/vio2sf/desmume/SPU.cpp
	${BASE_DIR}/src/vio2sf/desmume/thumb_instructions.c

	${BASE_DIR}/src/plugins/vio2sf/zlib/adler32.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/crc32.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/infback.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/inffast.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/inflate.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/inftrees.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/uncompr.c
	${BASE_DIR}/src/plugins/vio2sf/zlib/zutil.c

	${BASE_DIR}/src/plugins/xsfc/xsfdrv.c
	${BASE_DIR}/src/plugins/vio2sf/desmume/soundView.cpp
)

set(NOSTDLIBC++_ENABLED ON)
if(NOSTDLIBC++_ENABLED)
	set(SOURCES ${SOURCES} ${BASE_DIR}/src/plugins/custom/nostdc++.cpp)
	list(APPEND LINK_OPTIONS -nostdlib++)
	# target_compile_options(${TARGET_NAME} PUBLIC  $<$<COMPILE_LANGUAGE:CXX>:-nostdlib++>)
endif()


if(WIN32)
	list(APPEND EXTRA_SOURCES
		${BASE_DIR}/vio2sf_core.def
		${BASE_DIR}/src/plugins/xsfc/xsfui.rc
	)
else()
	message(FATAL_ERROR "This project currently supports Windows targets only.")
endif()


add_library(${TARGET_NAME} SHARED ${SOURCES} ${EXTRA_SOURCES})

target_include_directories(${TARGET_NAME} PRIVATE
	${BASE_DIR}/src/vio2sf
	${BASE_DIR}/src/vio2sf/desmume
	${BASE_DIR}/src/plugins/vio2sf/zlib
	${BASE_DIR}/src/plugins/xsfc
)
if(NOT MSVC)
	list(APPEND COMPILE_OPTIONS -fomit-frame-pointer)
	list(APPEND COMPILE_OPTIONS -fno-exceptions)
	list(APPEND COMPILE_OPTIONS -fno-asynchronous-unwind-tables -fno-unwind-tables)
	list(APPEND COMPILE_OPTIONS -ffunction-sections -fdata-sections)
	list(APPEND COMPILE_OPTIONS -v)
	
	target_compile_options(${TARGET_NAME} PUBLIC  $<$<COMPILE_LANGUAGE:CXX>:-fno-rtti>)

	list(APPEND LINK_OPTIONS -Wl,-Map=${TARGET_NAME}.map)
	list(APPEND LINK_OPTIONS -static-libgcc)
	# list(APPEND LINK_OPTIONS -static-libstdc++)
	list(APPEND LINK_OPTIONS -Wl,-cref)
	list(APPEND LINK_OPTIONS -Wl,--enable-stdcall-fixup)
	list(APPEND LINK_OPTIONS -Wl,--gc-sections)
	list(APPEND LINK_OPTIONS -v)
	
	if(CMAKE_BUILD_TYPE STREQUAL "Debug")
		list(APPEND LINK_OPTIONS -fstack-protector)
		list(APPEND LIBS PRIVATE ssp)
	else()
		# list(APPEND COMPILE_OPTIONS -flto)
		list(APPEND COMPILE_OPTIONS -Os)
	endif()
else()
	list(APPEND LINK_OPTIONS "/MAP:${TARGET_NAME}.map")
endif()

target_compile_options(${TARGET_NAME} PUBLIC ${COMPILE_OPTIONS})
target_link_options(${TARGET_NAME} PUBLIC ${LINK_OPTIONS})
target_link_libraries(${TARGET_NAME} PRIVATE ${LIBS})

install(TARGETS ${TARGET_NAME}
	RUNTIME DESTINATION bin
	LIBRARY DESTINATION lib
	ARCHIVE DESTINATION lib
)
