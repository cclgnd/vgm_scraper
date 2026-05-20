cmake_minimum_required(VERSION 2.8)

project(trim2sflib C CXX)

link_directories(${CMAKE_CURRENT_LIST_DIR}/../../../psflib)

find_package(ZLIB REQUIRED)

if(MSVC)
    option(STATIC_CRT "Use static CRT libraries" OFF)

    # Rewrite command line flags to use /MT if necessary
    if(STATIC_CRT)
        foreach(flag_var
                CMAKE_CXX_FLAGS CMAKE_CXX_FLAGS_DEBUG CMAKE_CXX_FLAGS_RELEASE
                CMAKE_CXX_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_RELWITHDEBINFO)
            if(${flag_var} MATCHES "/MD")
                string(REGEX REPLACE "/MD" "/MT" ${flag_var} "${${flag_var}}")
            endif(${flag_var} MATCHES "/MD")
        endforeach(flag_var)
    endif()
endif()

#============================================================================
# trim2sflib
#============================================================================

set(SRCS
    trim2sflib.c
    desmume/FIFO.c
    desmume/GPU.c
    desmume/MMU.c
    desmume/NDSSystem.c
    desmume/SPU.cpp
    desmume/arm_instructions.c
    desmume/armcpu.c
    desmume/barray.c
    desmume/bios.c
    desmume/cp15.c
    desmume/isqrt.c
    desmume/matrix.c
    desmume/mc.c
    desmume/resampler.c
    desmume/state.c
    desmume/thumb_instructions.c
)

add_executable(trim2sflib ${SRCS})

if(ZLIB_FOUND)
    include_directories(${ZLIB_INCLUDE_DIRS})
    target_link_libraries(trim2sflib psflib ${ZLIB_LIBRARIES})
endif(ZLIB_FOUND)
