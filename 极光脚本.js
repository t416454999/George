/* ============================================================
   极光引擎 - 前端主脚本
   功能：SPA路由、文章渲染、搜索筛选、分页加载
   ============================================================ */

// --- 全局状态 ---
const 状态 = {
    当前页面: '首页',
    当前分类: '全部',
    排序方式: '最新',
    每页数量: 12,
    已显示数量: 0,
    搜索关键词: '',
    文章列表: [],
    已筛选文章: [],
    来源集合: new Set(),
    当前文章ID: null,
};

// --- 初始化 ---
document.addEventListener('DOMContentLoaded', async () => {
    await 初始化数据();
    初始化路由();
    渲染当前页面();
    监听滚动();
});

// --- 数据初始化 ---
async function 初始化数据() {
    try {
        const 响应 = await fetch('文章数据库.json?v=' + Date.now());
        if (响应.ok) {
            const 数据 = await 响应.json();
            if (Array.isArray(数据)) {
                状态.文章列表 = 数据;
                console.log('文章数据库加载成功，共 ' + 数据.length + ' 篇');
            }
        } else {
            console.warn('文章数据库加载失败，状态码：' + 响应.status);
            状态.文章列表 = [];
        }
    } catch (错误) {
        console.warn('文章数据库加载异常：' + 错误.message);
        状态.文章列表 = [];
    }

    // 收集来源信息
    状态.文章列表.forEach(文章 => {
        状态.来源集合.add(文章.来源);
    });

    // 更新统计
    更新统计();
    更新来源标签();
    更新分类计数();
    更新更新时间();
}

function 更新统计() {
    const 总数 = 状态.文章列表.length;
    const 今日 = 状态.文章列表.filter(a => {
        try { return a.日期 && a.日期.includes(获取今日日期()); } catch { return false; }
    }).length;

    const el总数 = document.getElementById('文章总数');
    const el今日 = document.getElementById('今日新增');
    const el来源 = document.getElementById('覆盖来源');
    if (el总数) el总数.textContent = 总数;
    if (el今日) el今日.textContent = 今日;
    if (el来源) el来源.textContent = 状态.来源集合.size;
}

function 获取今日日期() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function 更新来源标签() {
    const 容器 = document.getElementById('来源标签');
    if (!容器) return;
    容器.innerHTML = Array.from(状态.来源集合).sort().map(s =>
        `<span class="来源标签项">📡 ${s}</span>`
    ).join('');
}

function 更新分类计数() {
    const 分类列表 = ['大模型', 'AI应用', 'AI绘画', '学术前沿', '行业动态', '开源工具'];
    分类列表.forEach(分类 => {
        const 计数 = 状态.文章列表.filter(a => a.分类 === 分类).length;
        const 元素 = document.getElementById(`计数-${分类}`);
        if (元素) 元素.textContent = `${计数}篇`;
    });
}

function 更新更新时间() {
    const 元素 = document.getElementById('更新时间');
    if (元素 && 状态.文章列表.length > 0) {
        const 最新文章 = 状态.文章列表[0];
        元素.textContent = `更新于：${最新文章.日期 || '未知'}`;
    }
}

// --- 路由管理 ---
function 初始化路由() {
    // 处理初始hash
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('详情/')) {
        const id = parseInt(hash.split('详情/')[1]);
        if (id) {
            状态.当前文章ID = id;
            显示文章详情();
            return;
        }
    }
    if (hash && ['首页','分类','搜索','关于'].includes(hash)) {
        切换页面(hash);
    } else {
        切换页面('首页');
    }

    window.addEventListener('hashchange', () => {
        const newHash = window.location.hash.slice(1);
        if (newHash.startsWith('详情/')) {
            const id = parseInt(newHash.split('详情/')[1]);
            if (id) {
                状态.当前文章ID = id;
                显示文章详情();
                return;
            }
        }
        if (newHash && ['首页','分类','搜索','关于'].includes(newHash)) {
            切换页面(newHash);
        } else if (!newHash.startsWith('详情/')) {
            切换页面('首页');
        }
    });
}

function 切换页面(页面名) {
    状态.当前页面 = 页面名;
    状态.当前文章ID = null;

    // 隐藏所有视图
    document.querySelectorAll('.页面视图').forEach(v => v.classList.remove('活跃视图'));

    // 显示目标视图
    const 视图映射 = {
        '首页': '首页视图',
        '分类': '分类视图',
        '搜索': '搜索视图',
        '关于': '关于视图',
    };

    const 视图ID = 视图映射[页面名];
    if (视图ID) {
        const 视图 = document.getElementById(视图ID);
        if (视图) 视图.classList.add('活跃视图');
    }

    // 更新导航高亮
    document.querySelectorAll('.导航链接').forEach(link => {
        link.classList.toggle('活跃', link.dataset.page === 页面名);
    });

    // 更新hash（不触发循环）
    if (window.location.hash.slice(1) !== 页面名) {
        history.replaceState(null, '', '#' + 页面名);
    }

    // 渲染内容
    状态.已显示数量 = 0;
    switch (页面名) {
        case '首页': 渲染首页(); break;
        case '分类': 更新分类计数(); break;
        case '搜索': 初始化搜索(); break;
    }

    // 关闭移动菜单
    const 菜单 = document.getElementById('导航菜单');
    const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.remove('展开');
    if (按钮) 按钮.classList.remove('展开');

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- 首页渲染 ---
function 渲染首页() {
    const 加载区域 = document.getElementById('加载区域');
    if (加载区域) 加载区域.style.display = 'block';
    应用筛选();
}

function 应用筛选() {
    let 文章列表 = [...状态.文章列表];

    if (状态.当前分类 !== '全部') {
        文章列表 = 文章列表.filter(a => a.分类 === 状态.当前分类);
    }

    if (状态.排序方式 === '最热') {
        文章列表.sort((a, b) => (b.热度 || 0) - (a.热度 || 0));
    }

    状态.已筛选文章 = 文章列表;
    状态.已显示数量 = 0;

    const 网格 = document.getElementById('文章网格');
    const 空状态 = document.getElementById('空状态');
    const 加载区域 = document.getElementById('加载区域');

    if (!网格) return;
    网格.innerHTML = '';

    if (文章列表.length === 0) {
        if (空状态) 空状态.style.display = 'block';
        if (加载区域) 加载区域.style.display = 'none';
    } else {
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'block';
        加载更多();
    }
}

function 创建文章卡片(文章) {
    const 卡片 = document.createElement('article');
    卡片.className = '文章卡片';
    卡片.onclick = () => 打开文章详情(文章);

    const 日期 = 文章.日期 || '未知日期';
    const 分类 = 文章.分类 || 'AI资讯';
    const 来源 = 文章.来源 || '未知来源';

    卡片.innerHTML = `
        <div class="文章卡片头部">
            <span class="文章来源标签">📡 ${来源}</span>
            <span class="文章日期">📅 ${日期}</span>
        </div>
        <h3 class="文章标题">${文章.标题 || '无标题'}</h3>
        <p class="文章摘要">${文章.摘要 || '暂无摘要'}</p>
        <div class="文章卡片底部">
            <span class="文章分类标签">🏷️ ${分类}</span>
            <span class="文章阅读链接">阅读全文 →</span>
        </div>
    `;

    return 卡片;
}

function 加载更多() {
    const 网格 = document.getElementById('文章网格');
    const 按钮 = document.getElementById('加载更多按钮');
    if (!网格 || !按钮) return;

    const start = 状态.已显示数量;
    const end = Math.min(start + 状态.每页数量, 状态.已筛选文章.length);

    if (start >= 状态.已筛选文章.length) {
        按钮.disabled = true;
        按钮.textContent = `已加载全部 ${状态.已筛选文章.length} 篇资讯 ✓`;
        return;
    }

    for (let i = start; i < end; i++) {
        网格.appendChild(创建文章卡片(状态.已筛选文章[i]));
    }

    状态.已显示数量 = end;

    if (end >= 状态.已筛选文章.length) {
        按钮.disabled = true;
        按钮.textContent = `已加载全部 ${状态.已筛选文章.length} 篇资讯 ✓`;
    } else {
        按钮.disabled = false;
        按钮.textContent = `查看更多 (已显示${end}/${状态.已筛选文章.length}) ↓`;
    }
}

// --- 分类筛选 ---
function 筛选分类(分类名) {
    状态.当前分类 = 分类名;
    状态.已显示数量 = 0;

    document.querySelectorAll('.分类标签').forEach(tag => {
        tag.classList.toggle('活跃', tag.textContent.trim().includes(分类名) || (分类名 === '全部' && tag.textContent.trim() === '全部'));
    });

    切换页面('首页');
}

// --- 排序切换 ---
function 切换排序(方式) {
    状态.排序方式 = 方式;
    document.getElementById('文章网格').innerHTML = '';
    document.getElementById('加载更多按钮').disabled = false;
    document.getElementById('加载更多按钮').textContent = '查看更多资讯 ↓';
    应用筛选();
}

// --- 搜索功能 ---
function 初始化搜索() {
    const 输入框 = document.getElementById('搜索输入框');
    if (输入框) {
        输入框.value = 状态.搜索关键词;
    }
    if (状态.搜索关键词) {
        执行搜索();
    }
}

function 实时搜索() {
    clearTimeout(window.搜索定时器);
    window.搜索定时器 = setTimeout(() => {
        执行搜索();
    }, 500);
}

function 快速搜索(关键词) {
    const 输入框 = document.getElementById('搜索输入框');
    if (输入框) 输入框.value = 关键词;
    状态.搜索关键词 = 关键词;
    执行搜索();
}

function 执行搜索() {
    const 输入框 = document.getElementById('搜索输入框');
    const 关键词 = 输入框 ? 输入框.value.trim() : '';
    状态.搜索关键词 = 关键词;

    const 结果容器 = document.getElementById('搜索结果');
    if (!结果容器) return;

    if (!关键词) {
        结果容器.innerHTML = '<p class="搜索提示">请输入关键词开始搜索</p>';
        return;
    }

    const 结果 = 状态.文章列表.filter(文章 => {
        const 搜索文本 = `${文章.标题} ${文章.摘要} ${文章.来源} ${文章.分类} ${文章.标签 ? 文章.标签.join(' ') : ''}`.toLowerCase();
        return 搜索文本.includes(关键词.toLowerCase());
    });

    if (结果.length === 0) {
        结果容器.innerHTML = `<div class="空状态"><span class="空状态图标">🔍</span><p>未找到与"${关键词}"相关的资讯</p></div>`;
        return;
    }

    结果容器.innerHTML = `
        <p style="margin-bottom:16px;color:var(--文字次)">
            找到 <strong style="color:var(--极光绿)">${结果.length}</strong> 篇与"<strong>${关键词}</strong>"相关的资讯
        </p>
        <div class="文章网格">
            ${结果.slice(0, 24).map(a => `
                <div class="文章卡片" onclick="打开文章详情ById(${a.id})">
                    <div class="文章卡片头部">
                        <span class="文章来源标签">📡 ${a.来源 || '未知'}</span>
                        <span class="文章日期">📅 ${a.日期 || '未知'}</span>
                    </div>
                    <h3 class="文章标题">${高亮关键词(a.标题, 关键词)}</h3>
                    <p class="文章摘要">${高亮关键词(a.摘要 || '', 关键词)}</p>
                    <div class="文章卡片底部">
                        <span class="文章分类标签">🏷️ ${a.分类 || 'AI资讯'}</span>
                        <span class="文章阅读链接">阅读全文 →</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function 高亮关键词(文本, 关键词) {
    if (!文本 || !关键词) return 文本 || '';
    const 转义关键词 = 关键词.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const 正则 = new RegExp(`(${转义关键词})`, 'gi');
    return 文本.replace(正则, '<mark style="background:rgba(0,229,160,0.3);color:#fff;padding:1px 4px;border-radius:3px">$1</mark>');
}

// --- 文章详情（直接切换，不用hash路由） ---
function 打开文章详情(文章) {
    if (!文章 || !文章.id) return;
    状态.当前文章ID = 文章.id;
    状态.当前页面 = '详情';
    history.pushState(null, '', '#详情/' + 文章.id);
    显示文章详情();
}

function 打开文章详情ById(id) {
    const 文章 = 状态.文章列表.find(a => a.id === id);
    if (!文章) return;
    打开文章详情(文章);
}

function 显示文章详情() {
    const id = 状态.当前文章ID;
    const 文章 = 状态.文章列表.find(a => a.id === id);

    if (!文章) {
        切换页面('首页');
        return;
    }

    // 隐藏所有视图
    document.querySelectorAll('.页面视图').forEach(v => v.classList.remove('活跃视图'));

    // 更新导航高亮（取消所有高亮）
    document.querySelectorAll('.导航链接').forEach(link => {
        link.classList.remove('活跃');
    });

    // 显示详情视图
    const 详情视图 = document.getElementById('详情视图');
    if (!详情视图) return;
    详情视图.classList.add('活跃视图');

    const 容器 = document.getElementById('详情容器');
    if (!容器) return;

    const 内容段落 = (文章.内容 || 文章.摘要 || '暂无详细内容')
        .split('\n')
        .filter(p => p.trim())
        .map(p => `<p>${p.trim()}</p>`)
        .join('');

    容器.innerHTML = `
        <button class="详情返回" onclick="切换页面('首页')">← 返回首页</button>
        <h1 class="详情标题">${文章.标题 || '无标题'}</h1>
        <div class="详情元信息">
            <span>📡 来源：${文章.来源 || '未知'}</span>
            <span>📅 日期：${文章.日期 || '未知'}</span>
            <span>🏷️ 分类：${文章.分类 || 'AI资讯'}</span>
            ${文章.热度 ? '<span>🔥 热度：' + 文章.热度 + '</span>' : ''}
        </div>
        <div class="详情正文">${内容段落 || '<p>暂无详细内容，请查看原文链接。</p>'}</div>
        ${文章.链接 ? '<a href="' + 文章.链接 + '" target="_blank" rel="noopener" class="详情来源链接">🔗 查看原文 →</a>' : ''}
    `;

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- 移动端菜单 ---
function 切换移动菜单() {
    const 菜单 = document.getElementById('导航菜单');
    const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.toggle('展开');
    if (按钮) 按钮.classList.toggle('展开');
}

// --- 滚动监听 ---
function 监听滚动() {
    const 返回按钮 = document.getElementById('返回顶部');
    const 导航栏 = document.getElementById('导航栏');
    let 上次滚动位置 = 0;

    window.addEventListener('scroll', () => {
        const 当前位置 = window.scrollY;

        if (返回按钮) {
            if (当前位置 > 600) {
                返回按钮.classList.add('可见');
            } else {
                返回按钮.classList.remove('可见');
            }
        }

        if (导航栏) {
            if (当前位置 > 上次滚动位置 && 当前位置 > 200) {
                导航栏.classList.add('隐藏');
            } else {
                导航栏.classList.remove('隐藏');
            }
        }
        上次滚动位置 = 当前位置;
    });
}

function 滚动到顶部() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- 浏览器后退按钮支持 ---
window.addEventListener('popstate', () => {
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('详情/')) {
        const id = parseInt(hash.split('详情/')[1]);
        if (id) {
            状态.当前文章ID = id;
            状态.当前页面 = '详情';
            显示文章详情();
            return;
        }
    }
    if (hash && ['首页','分类','搜索','关于'].includes(hash)) {
        切换页面(hash);
    } else {
        切换页面('首页');
    }
});
