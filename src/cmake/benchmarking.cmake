CMAKE_MINIMUM_REQUIRED(VERSION 3.0)

# CREATE_NAMED_BENCHMARK(foo bar.cc) creates a benchmark named `foo` from the
# file `bar.cc`.
MACRO(CREATE_NAMED_BENCHMARK NAME FILENAME)
    ADD_EXECUTABLE(${NAME} ${FILENAME})
    ADD_TEST(NAME ${NAME} COMMAND ${NAME})
    SET_TESTS_PROPERTIES(${NAME} PROPERTIES LABELS "BENCHMARK")
    ADD_DEPENDENCIES(${NAME}
        googlebenchmark
        googlelog)
    TARGET_LINK_LIBRARIES(${NAME}
        googlebenchmark
        googlelog
        pthread)
ENDMACRO(CREATE_NAMED_BENCHMARK)

# CREATE_BENCHMARK(foo) creates a benchmark named `foo` from the file `foo.cc`.
MACRO(CREATE_BENCHMARK NAME)
    CREATE_NAMED_BENCHMARK(${NAME} ${NAME}.cc)
ENDMACRO(CREATE_BENCHMARK)
