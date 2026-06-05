/* ============================================================
   极光引擎 · Aurora Engine — 前端脚本
   SPA路由 / 文章渲染（头条→次条→列表）/ 搜索 / 筛选
   最后修改：见 修改登记.json
   ============================================================ */

// --- 全局状态 ---
const 状态 = {
    当前页面: '首页',
    当前分类: '全部',
    排序方式: '最新',
    每页数量: 20,
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
    监听滚动();
});

// ============================================================
// 数据加载
// ============================================================

async function 初始化数据() {
    // 来源白名单 — 只显示真正的AI资讯来源
    const AI来源白名单 = [
        'The Information', 'Stratechery', 'Anthropic Blog', 'CVPR 2026 现场报道',
        'World Arena 独家访谈', 'Stanford HAI', 'The Verge', 'ArXiv 论文解读',
        'Steersman AI Blog', 'AI Developer Survey', '机器之心', '量子位', '36氪',
        '雷锋网', '虎嗅', 'Google Research', 'Google DeepMind', 'Meta AI Blog',
        'Figure AI Blog', 'Variety', 'OpenAI Blog'
    ];

    try {
        const 响应 = await fetch('文章数据库.json?v=' + Date.now());
        if (响应.ok) {
            const 数据 = await 响应.json();
            if (Array.isArray(数据)) {
                // 只保留AI资讯来源的文章
                状态.文章列表 = 数据.filter(a => AI来源白名单.includes(a.来源));
                const 被过滤 = 数据.length - 状态.文章列表.length;
                if (被过滤 > 0) {
                    console.log('已过滤 ' + 被过滤 + ' 篇非AI资讯');
                }
                console.log('文章数据库加载成功，共 ' + 状态.文章列表.length + ' 篇');
            }
        } else {
            console.warn('文章数据库加载失败，状态码：' + 响应.status);
            状态.文章列表 = [];
        }
    } catch (错误) {
        console.warn('文章数据库加载异常：' + 错误.message);
        状态.文章列表 = [];
    }

    状态.文章列表.forEach(文章 => {
        状态.来源集合.add(文章.来源);
    });

    更新统计();
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

function 更新分类计数() {
    const 分类列表 = ['大模型', 'AI应用', 'AI绘画', '学术前沿', '行业动态', '开源工具', '原生资讯'];
    分类列表.forEach(分类 => {
        const 计数 = 状态.文章列表.filter(a => a.分类 === 分类).length;
        const 元素 = document.getElementById(`计数-${分类}`);
        if (元素) 元素.textContent = `${计数} 篇`;
    });
}

function 更新更新时间() {
    const 元素 = document.getElementById('更新时间');
    if (元素 && 状态.文章列表.length > 0) {
        const 最新文章 = 状态.文章列表[0];
        元素.textContent = `更新于：${最新文章.日期 || '未知'}`;
    }
}

// ============================================================
// 路由
// ============================================================

function 初始化路由() {
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('详情/')) {
        const id = parseInt(hash.split('详情/')[1]);
        if (id) { 状态.当前文章ID = id; 显示文章详情(); return; }
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
            if (id) { 状态.当前文章ID = id; 显示文章详情(); return; }
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

    document.querySelectorAll('.页面视图').forEach(v => v.classList.remove('活跃视图'));

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

    document.querySelectorAll('.导航链接').forEach(link => {
        link.classList.toggle('活跃', link.dataset.page === 页面名);
    });

    if (window.location.hash.slice(1) !== 页面名) {
        history.replaceState(null, '', '#' + 页面名);
    }

    状态.已显示数量 = 0;
    switch (页面名) {
        case '首页': 渲染首页(); break;
        case '分类': 更新分类计数(); break;
        case '搜索': 初始化搜索(); break;
    }

    const 菜单 = document.getElementById('导航菜单');
    const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.remove('展开');
    if (按钮) 按钮.classList.remove('展开');

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================
// 首页渲染 — 新布局：头条卡片 → 次条双栏 → 紧凑列表
// ============================================================

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

    // 确保头条是热度最高或最新的高价值内容
    // 已有排序：最新在前（默认），或热度优先
    // 针对头条：在前2篇中选热度最高的作为头条
    if (文章列表.length >= 2) {
        const 前两篇 = 文章列表.slice(0, 2);
        const 头条索引 = 前两篇[0].热度 >= 前两篇[1].热度 ? 0 : 1;
        if (头条索引 === 1) {
            // 交换：把热度高的放第一
            [文章列表[0], 文章列表[1]] = [文章列表[1], 文章列表[0]];
        }
    }

    状态.已筛选文章 = 文章列表;
    状态.已显示数量 = 0;

    const 空状态 = document.getElementById('空状态');
    const 加载区域 = document.getElementById('加载区域');

    if (文章列表.length === 0) {
        if (空状态) 空状态.style.display = 'block';
        if (加载区域) 加载区域.style.display = 'none';
        clearContainers();
    } else {
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'block';
        加载更多();
    }
}

function clearContainers() {
    const ids = ['头条容器', '次条容器', '列表容器'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '';
    });
}

function 加载更多() {
    const 按钮 = document.getElementById('加载更多按钮');
    if (!按钮) return;

    const start = 状态.已显示数量;
    const end = Math.min(start + 状态.每页数量, 状态.已筛选文章.length);

    if (start >= 状态.已筛选文章.length) {
        按钮.disabled = true;
        按钮.textContent = `已加载全部 ${状态.已筛选文章.length} 篇`;
        return;
    }

    渲染文章区块(状态.已筛选文章.slice(start, end), start === 0);

    状态.已显示数量 = end;

    if (end >= 状态.已筛选文章.length) {
        按钮.disabled = true;
        按钮.textContent = `已加载全部 ${状态.已筛选文章.length} 篇`;
    } else {
        按钮.disabled = false;
        按钮.textContent = `加载更多（已显示 ${end}/${状态.已筛选文章.length}）`;
    }
}

/**
 * 核心渲染函数：首页布局 = 头条大卡 + 次条双栏 + 紧凑列表
 * 只在首次加载（start === 0）时重建布局
 */
function 渲染文章区块(文章批次, 是首次加载) {
    if (是首次加载) {
        clearContainers();

        if (文章批次.length === 0) return;

        // 1. 头条（第1篇）
        const 头条容器 = document.getElementById('头条容器');
        if (头条容器 && 文章批次.length >= 1) {
            头条容器.appendChild(创建头条卡片(文章批次[0]));
        }

        // 2. 次条双栏（第2-3篇）
        if (文章批次.length >= 2) {
            const 次条容器 = document.getElementById('次条容器');
            if (次条容器) {
                const 次条结束 = Math.min(3, 文章批次.length);
                for (let i = 1; i < 次条结束; i++) {
                    次条容器.appendChild(创建次条卡片(文章批次[i]));
                }
            }
        }

        // 3. 紧凑列表（第4篇起）
        if (文章批次.length > 3) {
            const 列表容器 = document.getElementById('列表容器');
            if (列表容器) {
                // 列表标题
                const 标题 = document.createElement('div');
                标题.className = '列表区域标题';
                标题.textContent = '更多资讯';
                列表容器.appendChild(标题);

                const 列表 = document.createElement('ul');
                列表.className = '资讯列表';
                列表.id = '资讯列表';

                for (let i = 3; i < 文章批次.length; i++) {
                    列表.appendChild(创建列表项(文章批次[i]));
                }
                列表容器.appendChild(列表);
            }
        }
    } else {
        // 非首次加载：追加到已有列表
        const 列表 = document.getElementById('资讯列表');
        if (列表 && 文章批次.length > 0) {
            文章批次.forEach(文章 => {
                列表.appendChild(创建列表项(文章));
            });
        }
    }
}

// ============================================================
// 卡片构建函数
// ============================================================

/** 头条大卡片 */
function 创建头条卡片(文章) {
    const 卡片 = document.createElement('article');
    卡片.className = '头条卡片';
    卡片.onclick = () => 打开文章详情(文章);

    const 标签HTML = (文章.标签 || []).map(t => `<span class="头条标签">${t}</span>`).join('');

    卡片.innerHTML = `
        <div class="头条元信息">
            <span class="头条来源">${文章.来源 || '未知来源'}</span>
            <span class="头条日期">${文章.日期 || '未知日期'}</span>
            <span class="头条分类">${文章.分类 || 'AI资讯'}</span>
        </div>
        <h2 class="头条标题">${文章.标题 || '无标题'}</h2>
        <p class="头条摘要">${文章.摘要 || 文章.内容 || ''}</p>
        ${标签HTML ? '<div class="头条标签栏">' + 标签HTML + '</div>' : ''}
    `;

    return 卡片;
}

/** 次条两栏卡片 */
function 创建次条卡片(文章) {
    const 卡片 = document.createElement('article');
    卡片.className = '次条卡片';
    卡片.onclick = () => 打开文章详情(文章);

    卡片.innerHTML = `
        <div class="次条来源">${文章.来源 || '未知来源'}</div>
        <h3 class="次条标题">${文章.标题 || '无标题'}</h3>
        <p class="次条摘要">${文章.摘要 || 文章.内容 || ''}</p>
        <div class="次条元信息">
            <span>${文章.日期 || ''}</span>
            <span>${文章.分类 || ''}</span>
            ${文章.热度 ? '<span>热度 ' + 文章.热度 + '</span>' : ''}
        </div>
    `;

    return 卡片;
}

/** 紧凑列表项 */
function 创建列表项(文章) {
    const 项 = document.createElement('li');
    项.className = '资讯列表项';

    const 链接 = document.createElement('a');
    链接.className = '资讯列表链接';
    链接.href = '#详情/' + 文章.id;
    链接.onclick = (e) => {
        e.preventDefault();
        打开文章详情(文章);
    };

    链接.innerHTML = `
        <div class="列表元信息">
            <span class="列表来源">${文章.来源 || ''}</span>
            <span class="列表分隔">·</span>
            <span class="列表日期">${文章.日期 || ''}</span>
        </div>
        <span class="列表标题">${文章.标题 || '无标题'}</span>
        <span class="列表分类">${文章.分类 || ''}</span>
    `;

    项.appendChild(链接);
    return 项;
}

// ============================================================
// 分类与排序
// ============================================================

function 筛选分类(分类名) {
    状态.当前分类 = 分类名;
    状态.已显示数量 = 0;

    document.querySelectorAll('.分类标签').forEach(tag => {
        const text = tag.textContent.trim();
        tag.classList.toggle('活跃', text === 分类名 || (分类名 === '全部' && text === '全部'));
    });

    切换页面('首页');
}

function 切换排序(方式) {
    状态.排序方式 = 方式;
    状态.已显示数量 = 0;
    应用筛选();
}

// ============================================================
// 搜索
// ============================================================

function 初始化搜索() {
    const 输入框 = document.getElementById('搜索输入框');
    if (输入框) 输入框.value = 状态.搜索关键词;
    if (状态.搜索关键词) 执行搜索();
}

function 实时搜索() {
    clearTimeout(window.搜索定时器);
    window.搜索定时器 = setTimeout(() => 执行搜索(), 400);
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
        结果容器.innerHTML = '<p class="搜索提示">输入关键词开始搜索</p>';
        return;
    }

    const 结果 = 状态.文章列表.filter(文章 => {
        const 搜索文本 = `${文章.标题} ${文章.摘要} ${文章.内容} ${文章.来源} ${文章.分类} ${(文章.标签||[]).join(' ')}`.toLowerCase();
        return 搜索文本.includes(关键词.toLowerCase());
    });

    if (结果.length === 0) {
        结果容器.innerHTML = `<div class="空状态"><p>未找到与「${关键词}」相关的资讯</p></div>`;
        return;
    }

    结果容器.innerHTML = `
        <p style="margin-bottom:24px;color:var(--text-tertiary);font-size:var(--text-sm)">
            找到 <span style="color:var(--accent);font-weight:600">${结果.length}</span> 篇与「<span style="color:var(--text-secondary)">${关键词}</span>」相关
        </p>
    `;

    // 搜索结果用紧凑列表渲染
    const 列表 = document.createElement('ul');
    列表.className = '资讯列表';
    结果.slice(0, 30).forEach(a => {
        const 项 = document.createElement('li');
        项.className = '资讯列表项';
        项.innerHTML = `
            <a class="资讯列表链接" href="#详情/${a.id}" onclick="event.preventDefault();打开文章详情ById(${a.id})">
                <div class="列表元信息">
                    <span class="列表来源">${a.来源||''}</span>
                    <span class="列表分隔">·</span>
                    <span class="列表日期">${a.日期||''}</span>
                </div>
                <span class="列表标题">${高亮关键词(a.标题, 关键词)}</span>
                <span class="列表分类">${a.分类||''}</span>
            </a>
        `;
        列表.appendChild(项);
    });
    结果容器.appendChild(列表);
}

function 高亮关键词(文本, 关键词) {
    if (!文本 || !关键词) return 文本 || '';
    const 转义 = 关键词.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const 正则 = new RegExp(`(${转义})`, 'gi');
    return 文本.replace(正则, '<mark style="background:var(--accent-dim);color:var(--accent);padding:1px 2px">$1</mark>');
}

// ============================================================
// 文章详情
// ============================================================

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

    if (!文章) { 切换页面('首页'); return; }

    document.querySelectorAll('.页面视图').forEach(v => v.classList.remove('活跃视图'));
    document.querySelectorAll('.导航链接').forEach(link => link.classList.remove('活跃'));

    const 详情视图 = document.getElementById('详情视图');
    if (!详情视图) return;
    详情视图.classList.add('活跃视图');

    const 容器 = document.getElementById('详情容器');
    if (!容器) return;

    const 内容段落 = (文章.内容 || 文章.摘要 || '暂无详细内容，请查看原文。')
        .split('\n')
        .filter(p => p.trim())
        .map(p => {
            // 简单的 markdown 风格标题识别
            if (p.trim().match(/^#{1,3}\s/)) {
                const level = p.trim().match(/^(#{1,3})/)[1].length;
                const text = p.trim().replace(/^#{1,3}\s/, '');
                const tag = level === 1 ? 'h2' : 'h3';
                return `<${tag}>${text}</${tag}>`;
            }
            return `<p>${p.trim()}</p>`;
        })
        .join('');

    容器.innerHTML = `
        <button class="详情返回" onclick="切换页面('首页')">&larr; 返回</button>
        <h1 class="详情标题">${文章.标题 || '无标题'}</h1>
        <div class="详情元信息">
            <span>来源：${文章.来源 || '未知'}</span>
            <span>${文章.日期 || '未知日期'}</span>
            <span>分类：${文章.分类 || 'AI资讯'}</span>
            ${文章.热度 ? '<span>热度 ' + 文章.热度 + '</span>' : ''}
        </div>
        <div class="详情正文">${内容段落 || '<p>暂无详细内容。</p>'}</div>
        ${文章.链接 ? '<a href="' + 文章.链接 + '" target="_blank" rel="noopener" class="详情来源链接">阅读原文 &rarr;</a>' : ''}
    `;

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================
// 移动端菜单
// ============================================================

function 切换移动菜单() {
    const 菜单 = document.getElementById('导航菜单');
    const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.toggle('展开');
    if (按钮) 按钮.classList.toggle('展开');
}

// ============================================================
// 滚动监听
// ============================================================

function 监听滚动() {
    const 返回按钮 = document.getElementById('返回顶部');
    const 导航栏 = document.getElementById('导航栏');
    let 上次滚动位置 = 0;

    window.addEventListener('scroll', () => {
        const 当前位置 = window.scrollY;

        if (返回按钮) {
            返回按钮.classList.toggle('可见', 当前位置 > 600);
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

// ============================================================
// 浏览器后退
// ============================================================

window.addEventListener('popstate', () => {
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('详情/')) {
        const id = parseInt(hash.split('详情/')[1]);
        if (id) { 状态.当前文章ID = id; 状态.当前页面 = '详情'; 显示文章详情(); return; }
    }
    if (hash && ['首页','分类','搜索','关于'].includes(hash)) {
        切换页面(hash);
    } else {
        切换页面('首页');
    }
});
