


// ; 给定一个字符串 s ，请你找出其中不含有重复字符的 最长 子串 的长度。

 

// ; 示例 1:

// ; 输入: s = "abcabcbb"
// ; 输出: 3 
// ; 解释: 因为无重复字符的最长子串是 "abc"，所以其长度为 3。注意 "bca" 和 "cab" 也是正确答案。
// ; 示例 2:

// ; 输入: s = "bbbbb"
// ; 输出: 1
// ; 解释: 因为无重复字符的最长子串是 "b"，所以其长度为 1。
// ; 示例 3:

// ; 输入: s = "pwwkew"
// ; 输出: 3
// ; 解释: 因为无重复字符的最长子串是 "wke"，所以其长度为 3。
// ;      请注意，你的答案必须是 子串 的长度，"pwke" 是一个子序列，不是子串。


#include <string>
#include <unordered_map>
//@brief 返回最长无重复子串
int getLongSeqStr(const std::string &str)
{
    if(str.empty()){
        return 0;
    }
    
    int left = 0;
    int maxLen = 0;
    std::unordered_map<char, int> charIndex; // 存储字符最后出现的位置
    
    for(int right = 0; right < str.size(); ++right)
    {
        char currentChar = str[right];
        
        // 如果当前字符已存在且在当前窗口内
        if(charIndex.find(currentChar) != charIndex.end() && 
           charIndex[currentChar] >= left){
            left = charIndex[currentChar] + 1; // 移动左指针到重复字符的下一位
        }
        
        charIndex[currentChar] = right; // 更新字符位置
        maxLen = std::max(maxLen, right - left + 1); // 更新最大长度
    }
    
    return maxLen;
}