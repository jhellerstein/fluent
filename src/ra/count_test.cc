#include "ra/count.h"

#include <tuple>
#include <utility>
#include <vector>

#include "gmock/gmock.h"
#include "gtest/gtest.h"
#include "range/v3/all.hpp"

#include "ra/iterable.h"
#include "testing/test_util.h"

namespace fluent {

TEST(Count, EmptyCount) {
  std::vector<std::tuple<int>> xs = {};
  auto count = ra::make_count(ra::make_iterable(&xs));
  const std::set<std::tuple<int>> expected = {{0}};
  ExpectRngsEqual(count.ToPhysical().ToRange(), expected);
}

TEST(Count, SimpleCount) {
  std::vector<std::tuple<int>> xs = {{1}, {2}, {3}};
  auto count = ra::make_count(ra::make_iterable(&xs));
  const std::set<std::tuple<int>> expected = {{3}};
  ExpectRngsEqual(count.ToPhysical().ToRange(), expected);
}

TEST(Count, SimplePipedCount) {
  std::vector<std::tuple<int>> xs = {{1}, {2}, {3}};
  auto count = ra::make_iterable(&xs) | ra::count();
  const std::set<std::tuple<int>> expected = {{3}};
  ExpectRngsEqual(count.ToPhysical().ToRange(), expected);
}

}  // namespace fluent

int main(int argc, char** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}