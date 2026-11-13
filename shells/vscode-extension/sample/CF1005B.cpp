// 範例檔：這份程式「故意」寫錯，用來看範例測資會怎麼回報 WA。
#include <algorithm>
#include <iostream>
#include <string>
using namespace std;

int main() {
    string s, t;
    cin >> s >> t;
    int k = 0;  // 故意寫錯：這裡比的是共同「前綴」，題目要的是共同後綴
    while (k < (int)min(s.size(), t.size()) && s[k] == t[k]) k++;
    cout << s.size() + t.size() - 2 * k << "\n";
}
