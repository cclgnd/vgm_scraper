#pragma once

#include <cstddef>
#include <utility>
#include <vector>

template <typename T>
class Index {
public:
    Index() = default;
    explicit Index(std::vector<T> data) : data_(std::move(data)) {}

    int len() const { return static_cast<int>(data_.size()); }
    T * begin() { return data_.empty() ? nullptr : data_.data(); }
    const T * begin() const { return data_.empty() ? nullptr : data_.data(); }

    void clear() { data_.clear(); }
    void append(const T * data, std::size_t size) { data_.insert(data_.end(), data, data + size); }

private:
    std::vector<T> data_;
};
