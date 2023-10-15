#include "tglang.h"
#include "symbols_to_replace.h"

#include "fastText/src/fasttext.h"

#include <atomic>
#include <string>
#include <vector>
#include <iostream>
#include <sstream>
#include <chrono>
#include <iomanip>
#include <cstdlib>
#include <cstring>
#include <codecvt>
#include <unordered_set>
#include <iterator>

#define LABEL_PREFIX "__label__"

using UnicodeConverter = std::wstring_convert<std::codecvt_utf8<char32_t>, char32_t>;

// TODO: remove profiler
struct ProfileIt {
  char const * const m_name = nullptr;
  std::chrono::steady_clock::time_point m_begin;
  
  ProfileIt(char const * const name) : m_name(name), m_begin(std::chrono::steady_clock::now()) {}

  ~ProfileIt() {
    auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - m_begin);
    std::cerr << m_name << std::fixed << std::setprecision(6) << (elapsed.count() * 0.000001) << " sec \n";
  }
};

struct LibResources {
  std::unordered_set<char32_t> to_replace;
  fasttext::FastText model;
  UnicodeConverter u_converter;

  LibResources() {
    ProfileIt p("Init");

    auto replace_begin = std::cbegin(SYMBOLS_TO_REPLACE);
    auto replace_end = std::cend(SYMBOLS_TO_REPLACE);

    to_replace.reserve(replace_end - replace_begin);
    to_replace.insert(replace_begin, replace_end);

    model.loadModel("./resources/fasttext-model.bin");
  }
};

LibResources lib_sources;

enum TglangLanguage tglang_detect_programming_language(const char *text) {
  std::stringstream ss;
  std::string preprocessed;
  {
    ProfileIt prep("Preprocessing");

    std::u32string unicode = lib_sources.u_converter.from_bytes(text, text + std::strlen(text));

    std::u32string replaced;
    replaced.reserve(unicode.size() * 2 + 1);
    for (size_t i = 0; i < unicode.size(); i++) {
      auto c = unicode[i];
      if (c == U'\n' && i > 0 && unicode[i-1] != U'\n') {
        replaced.append(U"!$");
      } else if (lib_sources.to_replace.find(c) == lib_sources.to_replace.end()) {
        replaced.push_back(c);
      }
    }

    preprocessed = lib_sources.u_converter.to_bytes(replaced.data(), replaced.data() + replaced.size());

    // std::cerr << "Processing << `" << preprocessed << "`\n";

    ss << preprocessed.c_str();

    ss.seekg(0, ss.beg);
  }

  constexpr int32_t kCount = 1;
  constexpr fasttext::real kProbThreshold = 0.3;

  int converted;
  std::vector<std::pair<fasttext::real, std::string>> result;
  {
    ProfileIt inf("Inference");
    try {
      lib_sources.model.predictLine(ss, result, kCount, kProbThreshold);
    } catch (...) {
      std::cerr << "EXCEPTION durint predict" << "\n";
      return TglangLanguage::TGLANG_LANGUAGE_OTHER;
    }

    if (result.empty()) {
      std::cerr << "No results!" << "\n";
      return TglangLanguage::TGLANG_LANGUAGE_OTHER;
    }

    auto const & res = result.front();

    // TODO: remove LABEL_PREFIX
    converted = std::atoi(res.second.c_str() + std::strlen(LABEL_PREFIX));

    // TODO: remove logs
    std::cerr << "Fasttext, class=" << res.second << ",converted=" << converted << ",prob=" << res.first << '\n';
    
    assert(converted <= TglangLanguage::TGLANG_LANGUAGE_YAML);
  }

  return static_cast<TglangLanguage>(converted);
}
