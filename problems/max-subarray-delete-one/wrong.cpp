// 一個「很自然但錯誤」的想法：先 Kadane 找最佳子陣列，再刪掉裡面最小的負數。
#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n; cin >> n;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    long long best = a[0], cur = a[0];
    int bl = 0, br = 0, cl = 0;
    for (int i = 1; i < n; i++) {
        if (cur + a[i] < a[i]) cur = a[i], cl = i; else cur += a[i];
        if (cur > best) best = cur, bl = cl, br = i;
    }
    long long mn = *min_element(a.begin() + bl, a.begin() + br + 1);
    if (mn < 0 && br > bl) best -= mn;
    cout << best << "\n";
}
