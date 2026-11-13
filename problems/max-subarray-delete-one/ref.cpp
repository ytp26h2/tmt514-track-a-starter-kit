#include <algorithm>
#include <climits>
#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n; cin >> n;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    const long long NEG = LLONG_MIN / 4;
    long long f0 = a[0], f1 = NEG, ans = a[0];
    for (int i = 1; i < n; i++) {
        long long n1 = max(f1 + a[i], f0);   // 已刪：延續，或刪掉 a[i]
        long long n0 = max(f0 + a[i], a[i]); // 未刪
        f0 = n0, f1 = n1;
        ans = max({ans, f0, f1});
    }
    cout << ans << "\n";
}
