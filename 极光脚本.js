/* ============================================================
   极光引擎 · 前端脚本
   布局：4等大卡片(2x2) → 一手消息(文字行) → 更多资讯(文字行) → GitHub工具
   最后修改：见 修改登记.json
   ============================================================ */

const 状态 = {
    当前页面: '首页', 当前分类: '全部', 排序方式: '最新',
    搜索关键词: '', 文章列表: [], 已筛选文章: [],
    来源集合: new Set(), 当前文章ID: null, 当前详情文章: null, 专题缓存: {},
    专题请求序号: 0, 专题请求控制器: null,
};

const 专题栏目文件 = {
    '国际形势': '国际形势.json',
    '世界杯': '世界杯.json',
    '人文艺术': '人文艺术.json',
    '情感': '情感.json',
};

document.addEventListener('DOMContentLoaded', async () => {
    await 初始化数据();
    初始化路由();
    监听滚动();
});

// ============================================================
// 数据加载
// ============================================================

async function 初始化数据() {
    const AI来源白名单 = [
        '36氪', 'Google DeepMind 官方', 'Hugging Face 官方',
        'OpenAI 官方', 'Anthropic 官方', 'arXiv AI', '新浪科技',
        '量子位', '雷锋网', 'GitHub 官方博客',
    ];

    try {
        const 响应 = await fetch('文章数据库.json?v=' + Date.now());
        if (响应.ok) {
            const 数据 = await 响应.json();
            if (Array.isArray(数据)) {
                状态.文章列表 = 数据.filter(a => AI来源白名单.includes(a.来源));
                const 被过滤 = 数据.length - 状态.文章列表.length;
                if (被过滤 > 0) console.log('已过滤 ' + 被过滤 + ' 篇非AI资讯');
                console.log('文章数据库加载成功，共 ' + 状态.文章列表.length + ' 篇');
            }
        } else {
            状态.文章列表 = [];
        }
    } catch (错误) {
        console.warn('文章数据库加载异常：' + 错误.message);
        状态.文章列表 = [];
    }

    状态.文章列表.forEach(文章 => { 状态.来源集合.add(文章.来源); });
    更新统计();
    更新更新时间();
}

function 更新统计() {
    const 总数 = 状态.文章列表.length;
    const 今日 = 状态.文章列表.filter(a => { try { return a.日期 && a.日期.includes(获取今日日期()); } catch { return false; } }).length;
    ['文章总数','今日新增','覆盖来源'].forEach((id, i) => {
        const el = document.getElementById(id);
        if (el) 动画递增(el, [总数, 今日, 状态.来源集合.size][i]);
    });
}
function 动画递增(元素, 目标值, 时长 = 800) {
    const 开始 = performance.now();
    function 更新(时间) {
        const 进度 = Math.min((时间 - 开始) / 时长, 1);
        const 缓动 = 1 - Math.pow(1 - 进度, 3);
        元素.textContent = Math.floor(0 + (目标值 - 0) * 缓动);
        if (进度 < 1) requestAnimationFrame(更新);
        else 元素.textContent = 目标值;
    }
    requestAnimationFrame(更新);
}
function 获取今日日期() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function 更新更新时间() {
    const 元素 = document.getElementById('更新时间');
    if (元素 && 状态.文章列表.length > 0) {
        元素.textContent = '更新于：' + (状态.文章列表[0].日期 || '未知');
    }
}

// ============================================================
// 路由
// ============================================================

function 初始化路由() {
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('详情/')) { const id = parseInt(hash.split('详情/')[1]); if (id) { 状态.当前文章ID = id; 显示文章详情(); return; } }
    if (hash && ['首页','分类','搜索','关于'].includes(hash)) 切换页面(hash); else 切换页面('首页');
    window.addEventListener('hashchange', () => {
        const newHash = window.location.hash.slice(1);
        if (newHash.startsWith('详情/')) { const id = parseInt(newHash.split('详情/')[1]); if (id) { 状态.当前文章ID = id; 显示文章详情(); return; } }
        if (newHash && ['首页','分类','搜索','关于'].includes(newHash)) 切换页面(newHash);
        else if (!newHash.startsWith('详情/')) 切换页面('首页');
    });
}

function 切换页面(页面名) {
    状态.当前页面 = 页面名; 状态.当前文章ID = null;
    document.querySelectorAll('.页面视图').forEach(v => v.classList.remove('活跃视图'));
    const 视图映射 = { '首页':'首页视图','分类':'分类视图','搜索':'搜索视图','关于':'关于视图' };
    const 视图ID = 视图映射[页面名];
    if (视图ID) { const 视图 = document.getElementById(视图ID); if (视图) 视图.classList.add('活跃视图'); }
    document.querySelectorAll('.导航链接').forEach(link => { link.classList.toggle('活跃', link.dataset.page === 页面名); });
    if (window.location.hash.slice(1) !== 页面名) history.pushState(null, '', '#' + 页面名);
    switch (页面名) { case '首页': 渲染首页(); break; case '分类': 加载平台热点(); break; case '搜索': 初始化搜索(); break; }
    const 菜单 = document.getElementById('导航菜单'); const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.remove('展开'); if (按钮) 按钮.classList.remove('展开');
    if (!arguments[1]) window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================
// 首页渲染
// ============================================================

function 渲染首页() { 应用筛选(); }

function 应用筛选() {
    const 空状态 = document.getElementById('空状态');
    const 加载区域 = document.getElementById('加载区域');

    if (!专题栏目文件[状态.当前分类] && 状态.专题请求控制器) {
        状态.专题请求控制器.abort();
        状态.专题请求控制器 = null;
        状态.专题请求序号++;
    }

    // 独立分类：不走 AI 文章库过滤，读取各自的开放数据文件
    if (专题栏目文件[状态.当前分类]) {
        clearContainers(); 加载专题栏目(状态.当前分类);
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }
    if (状态.当前分类 === '行业热议') {
        clearContainers(); 加载行业热议();
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }
    if (状态.当前分类 === '金融') {
        clearContainers(); 加载金融热点();
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }
    if (状态.当前分类 === '工具排行') {
        clearContainers(); 加载工具排行();
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }
    if (状态.当前分类 === '一手消息') {
        clearContainers();
        const 一手来源 = ['OpenAI 官方', 'Google DeepMind 官方', 'Hugging Face 官方', 'arXiv AI', 'Anthropic 官方'];
        const 一手列表 = 状态.文章列表.filter(a => 一手来源.includes(a.来源));
        const 容器 = document.getElementById('特征容器');
        if (容器 && 一手列表.length > 0) {
            const 标题 = document.createElement('div'); 标题.className = '特征区标题'; 标题.textContent = '一手消息';
            容器.appendChild(标题);
            const 列表 = document.createElement('ul'); 列表.className = '一手列表';
            一手列表.forEach(a => 创建一手行(a, 列表));
            容器.appendChild(列表);
            // 默认折叠：只显示前5条
            const 限制数 = 5;
            for (let i = 限制数; i < 列表.children.length; i++) 列表.children[i].style.display = 'none';
            if (一手列表.length > 限制数) {
                const 折叠按钮 = document.createElement('button');
                折叠按钮.className = '加载更多按钮';
                折叠按钮.style.marginTop = '12px';
                const 多余 = 一手列表.length - 限制数;
                折叠按钮.textContent = `展开全部（${多余} 条）`;
                let 已展开 = false;
                折叠按钮.onclick = () => {
                    已展开 = !已展开;
                    for (let i = 限制数; i < 列表.children.length; i++) {
                        列表.children[i].style.display = 已展开 ? '' : 'none';
                    }
                    折叠按钮.textContent = 已展开 ? '收起' : `展开全部（${多余} 条）`;
                };
                容器.appendChild(折叠按钮);
            }
        }
        if (空状态) 空状态.style.display = 一手列表.length === 0 ? 'block' : 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }

    let 文章列表 = [...状态.文章列表];
    if (状态.当前分类 !== '全部') 文章列表 = 文章列表.filter(a => a.分类 === 状态.当前分类);
    if (状态.排序方式 === '最热') 文章列表.sort((a, b) => (b.热度 || 0) - (a.热度 || 0));

    if (文章列表.length === 0) {
        if (空状态) 空状态.style.display = 'block';
        if (加载区域) 加载区域.style.display = 'none';
        clearContainers();
    } else {
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';

        const 特征文章 = 文章列表.slice(0, 4);
        const 列表文章 = 文章列表.slice(4);

        渲染容器(状态.当前分类, 特征文章, 列表文章);
    }
}

// ============================================================
// 渲染区块
// ============================================================

function clearContainers() {
    ['特征容器','一手容器','列表容器','工具容器'].forEach(id => {
        const el = document.getElementById(id); if (el) el.innerHTML = '';
    });
}

function 安全外链(值) {
    try {
        const u = new URL(值, window.location.href);
        return ['http:', 'https:'].includes(u.protocol) ? u.href : '';
    } catch { return ''; }
}

function 添加文本元素(父元素, 标签, 类名, 文本) {
    const 元素 = document.createElement(标签);
    if (类名) 元素.className = 类名;
    元素.textContent = 文本 || '';
    父元素.appendChild(元素);
    return 元素;
}

async function 加载专题栏目(分类名) {
    const 容器 = document.getElementById('特征容器');
    if (!容器) return;
    const 请求序号 = ++状态.专题请求序号;
    if (状态.专题请求控制器) 状态.专题请求控制器.abort();
    const 请求控制器 = new AbortController();
    状态.专题请求控制器 = 请求控制器;
    添加文本元素(容器, 'div', '特征区标题', 分类名);

    let 数据 = 状态.专题缓存[分类名];
    if (!数据) {
        const 加载提示 = 添加文本元素(容器, 'div', '专题提示', '正在加载…');
        try {
            const 响应 = await fetch(专题栏目文件[分类名] + '?v=' + Date.now(), { signal: 请求控制器.signal });
            if (!响应.ok) throw new Error('HTTP ' + 响应.status);
            数据 = await 响应.json();
            if (请求序号 !== 状态.专题请求序号 || 状态.当前分类 !== 分类名) return;
            状态.专题缓存[分类名] = 数据;
        } catch (e) {
            if (e.name === 'AbortError' || 请求序号 !== 状态.专题请求序号) return;
            加载提示.textContent = '栏目暂时无法加载，请稍后刷新。';
            console.warn(分类名 + '加载失败：' + e.message);
            return;
        }
        加载提示.remove();
    }
    if (请求序号 !== 状态.专题请求序号 || 状态.当前分类 !== 分类名) return;

    const 说明 = document.createElement('div');
    说明.className = '专题说明';
    添加文本元素(说明, 'p', '专题说明文字', 数据.description || '');
    const 更新时间 = (数据.updated || '').replace('T', ' ').substring(0, 16);
    添加文本元素(说明, 'span', '专题更新时间', 更新时间 ? '更新于 ' + 更新时间 : '');
    容器.appendChild(说明);

    if (数据.message) {
        const 提示 = 添加文本元素(容器, 'div', '专题提示', 数据.message);
        if (数据.status === 'config_required') 提示.classList.add('待配置');
    }

    const 文章 = Array.isArray(数据.articles) ? 数据.articles : [];
    if (!文章.length) {
        添加文本元素(容器, 'div', '空状态', 分类名 === '世界杯' ? '世界杯数据源等待配置。' : '本栏目暂时没有数据。');
        return;
    }

    const 网格 = document.createElement('div'); 网格.className = '特征网格 专题网格';
    const 栏目主视觉 = 数据.主视觉 || 数据.封面 || 数据.cover || '';
    文章.slice(0, 4).forEach((条目, index) => {
        const 卡片 = 创建专题卡片(条目, index, 分类名, index === 0 ? 栏目主视觉 : '');
        if (index === 0) 卡片.classList.add('主推荐卡片'); else 卡片.classList.add('次推荐卡片');
        网格.appendChild(卡片);
    });
    容器.appendChild(网格);

    if (文章.length > 4) {
        const 列表容器 = document.getElementById('列表容器');
        添加文本元素(列表容器, 'div', '列表区域标题', 分类名 === '世界杯' ? '更多赛程' : '更多内容');
        const 列表 = document.createElement('ul'); 列表.className = '资讯列表 专题资讯列表';
        const 全部列表项 = 文章.slice(4).map(条目 => 创建专题列表项(条目));
        const 默认数量 = 8;
        全部列表项.slice(0, 默认数量).forEach(列表项 => 列表.appendChild(列表项));
        列表容器.appendChild(列表);
        const 折叠项 = 全部列表项.slice(默认数量);
        if (折叠项.length) {
            const 折叠按钮 = document.createElement('button');
            折叠按钮.className = '加载更多按钮';
            折叠按钮.style.marginTop = '12px';
            折叠按钮.textContent = `展开全部（${折叠项.length} 条）`;
            折叠按钮.setAttribute('aria-expanded', 'false');
            let 已展开 = false;
            折叠按钮.onclick = () => {
                已展开 = !已展开;
                if (已展开) 折叠项.forEach(列表项 => 列表.appendChild(列表项));
                else 折叠项.forEach(列表项 => 列表项.remove());
                折叠按钮.textContent = 已展开 ? '收起' : `展开全部（${折叠项.length} 条）`;
                折叠按钮.setAttribute('aria-expanded', String(已展开));
            };
            列表容器.appendChild(折叠按钮);
        }
    }
}

function 应用卡片主视觉(卡片, 文章, 分类名, 备用图片, index) {
    if (index !== 0) return;
    const 图片 = 安全外链(文章.封面 || 文章.图片 || 备用图片);
    卡片.classList.add('有主视觉', '分类主视觉-' + String(分类名 || '全部').replace(/[^\u4e00-\u9fa5A-Za-z0-9_-]/g, ''));
    if (!图片) return;
    卡片.classList.add('有图片');
    const 图框 = document.createElement('div'); 图框.className = '专题图片框';
    const img = document.createElement('img');
    img.src = 图片; img.alt = 文章.标题 || 分类名 || '栏目主视觉';
    img.loading = 'eager'; img.decoding = 'async'; img.fetchPriority = 'high';
    img.referrerPolicy = 'no-referrer';
    img.onerror = () => { 图框.remove(); 卡片.classList.remove('有图片'); };
    图框.appendChild(img); 卡片.prepend(图框);
}

function 转义HTML(值) {
    return String(值 == null ? '' : 值).replace(/[&<>"']/g, 字符 => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[字符]);
}

function 创建专题卡片(文章, index, 分类名, 备用图片) {
    const 卡片 = document.createElement('article');
    卡片.className = '特征卡片 专题卡片';
    卡片.dataset.index = String(index + 1).padStart(2, '0');
    卡片.tabIndex = 0;
    卡片.setAttribute('role', 'link');
    卡片.onclick = () => 打开文章详情(文章);
    卡片.onkeydown = e => { if (e.key === 'Enter') 卡片.click(); };
    const 图片 = index === 0 ? '' : 安全外链(文章.封面 || 文章.图片);
    if (图片) {
        卡片.classList.add('有图片');
        const 图框 = document.createElement('div'); 图框.className = '专题图片框';
        const img = document.createElement('img'); img.src = 图片; img.alt = 文章.标题 || '艺术作品';
        img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
        img.onerror = () => { 图框.remove(); 卡片.classList.remove('有图片'); };
        图框.appendChild(img); 卡片.appendChild(图框);
    }
    应用卡片主视觉(卡片, 文章, 分类名, 备用图片, index);
    const 信息 = document.createElement('div'); 信息.className = '卡片元信息';
    添加文本元素(信息, 'span', '卡片来源', 文章.来源 || '');
    添加文本元素(信息, 'span', '卡片日期', 文章.日期 || '');
    添加文本元素(信息, 'span', '卡片分类', 文章.分类 || '');
    卡片.appendChild(信息);
    添加文本元素(卡片, 'div', '卡片标题', 文章.标题 || '无标题');
    添加文本元素(卡片, 'div', '卡片摘要', (文章.摘要 || '').substring(0, 180));
    if (文章.版权) 添加文本元素(卡片, 'div', '专题版权', 文章.版权);
    return 卡片;
}

function 创建专题列表项(文章) {
    const 项 = document.createElement('li'); 项.className = '资讯列表项';
    const 链接 = document.createElement('a'); 链接.className = '资讯列表链接';
    链接.href = '#详情/' + 文章.id;
    链接.onclick = e => { e.preventDefault(); 打开文章详情(文章); };
    const 元信息 = document.createElement('div'); 元信息.className = '列表元信息';
    添加文本元素(元信息, 'span', '列表来源', 文章.来源 || '');
    添加文本元素(元信息, 'span', '列表分隔', '·');
    添加文本元素(元信息, 'span', '列表日期', 文章.日期 || '');
    链接.appendChild(元信息);
    添加文本元素(链接, 'span', '列表标题', 文章.标题 || '');
    添加文本元素(链接, 'span', '列表分类', 文章.分类 || '');
    项.appendChild(链接);
    return 项;
}

/** 统一渲染：特征卡片 + 更多资讯列表（默认8条折叠） */
function 渲染容器(分类, 特征文章, 列表文章) {
    clearContainers();

    // 特征区
    if (特征文章.length > 0) {
        const 容器 = document.getElementById('特征容器');
        if (容器) {
            const 标题 = document.createElement('div'); 标题.className = '特征区标题';
            标题.textContent = 分类 === '全部' ? '今日推荐' : 分类;
            容器.appendChild(标题);
            const 网格 = document.createElement('div'); 网格.className = '特征网格';
            特征文章.forEach((文章, index) => {
                const 卡片 = 创建特征卡片(文章);
                if (index === 0) {
                    卡片.classList.add('主推荐卡片');
                    应用卡片主视觉(卡片, 文章, 分类, 文章.主视觉 || 文章.封面 || '', index);
                }
                else 卡片.classList.add('次推荐卡片');
                卡片.dataset.index = String(index + 1).padStart(2, '0');
                网格.appendChild(卡片);
            });
            容器.appendChild(网格);
        }
    }

    // 更多资讯（默认8条折叠，带展开/收起）
    if (列表文章.length > 0) {
        const 容器 = document.getElementById('列表容器');
        if (容器) {
            const 标题 = document.createElement('div'); 标题.className = '列表区域标题'; 标题.textContent = '更多资讯';
            容器.appendChild(标题);
            const 列表 = document.createElement('ul'); 列表.className = '资讯列表';
            const 限制数 = 8;
            const allItems = 列表文章.map(文章 => createListLink(文章));
            const limited = allItems.slice(0, 限制数);
            const rest = allItems.slice(限制数);
            limited.forEach(el => 列表.appendChild(el));
            容器.appendChild(列表);
            if (rest.length > 0) {
                let 已展开 = false;
                const 折叠按钮 = document.createElement('button');
                折叠按钮.className = '加载更多按钮';
                折叠按钮.style.marginTop = '12px';
                折叠按钮.textContent = `展开全部（${rest.length} 条）`;
                折叠按钮.onclick = () => {
                    已展开 = !已展开;
                    if (已展开) {
                        rest.forEach(el => 列表.appendChild(el));
                        折叠按钮.textContent = '收起';
                    } else {
                        rest.forEach(el => el.remove());
                        折叠按钮.textContent = `展开全部（${rest.length} 条）`;
                    }
                };
                容器.appendChild(折叠按钮);
            }
        }
    }
}

function createListLink(文章) {
    const 项 = document.createElement('li'); 项.className = '资讯列表项';
    const 链接 = document.createElement('a'); 链接.className = '资讯列表链接';
    链接.href='#详情/'+文章.id; 链接.onclick=(e)=>{e.preventDefault();打开文章详情(文章);};
    链接.innerHTML=`<div class="列表元信息"><span class="列表来源">${文章.来源||''}</span><span class="列表分隔">·</span><span class="列表日期">${文章.日期||''}</span></div><span class="列表标题">${文章.标题||''}</span><span class="列表分类">${文章.分类||''}</span>`;
    项.appendChild(链接);
    return 项;
}

function append列表项(列表, 文章) { 列表.appendChild(createListLink(文章)); }

function 创建一手行(文章, 列表) {
    const 项 = document.createElement('li'); 项.className = '一手列表项';
    const 链接 = document.createElement('a'); 链接.className = '一手列表链接';
    链接.href='#详情/'+文章.id; 链接.onclick=(e)=>{e.preventDefault();打开文章详情(文章);};
    let html = `<span class="一手标记">一手</span><span class="一手来源">${文章.来源||''}</span><span class="一手日期">${文章.日期||''}</span>`;
    // 有翻译：显示中文标题 + 原标题副文本
    if (文章.原标题) {
        html += `<span class="一手标题文字">${文章.标题||''}</span>`;
        html += `<span class="一手原标题">${文章.原标题.replace(/【[^】]+】/g,'').trim()}</span>`;
        if (文章.中文提炼) {
            html += `<span class="一手要点">${文章.中文提炼.replace(/\n/g,'<br>')}</span>`;
        }
    } else {
        html += `<span class="一手标题文字">${文章.标题||''}</span>`;
    }
    链接.innerHTML = html;
    项.appendChild(链接); 列表.appendChild(项);
}

function 渲染特征区(文章列表) { /* 已合并到渲染容器 */ }

function 创建特征卡片(文章) {
    const 卡片 = document.createElement('article'); 卡片.className = '特征卡片';
    卡片.onclick = () => 打开文章详情(文章);
    const 标签HTML = (文章.标签 || []).slice(0, 3).map(t => `<span class="卡片标签">${t}</span>`).join('');
    卡片.innerHTML = `
        <div class="卡片元信息"><span class="卡片来源">${文章.来源||''}</span><span class="卡片日期">${文章.日期||''}</span><span class="卡片分类">${文章.分类||''}</span></div>
        <div class="卡片标题">${文章.标题||'无标题'}</div>
        <div class="卡片摘要">${(文章.摘要||'').substring(0,120)}</div>
        ${标签HTML ? '<div class="卡片标签栏">'+标签HTML+'</div>' : ''}`;
    return 卡片;
}

// ============================================================
// 金融热点
// ============================================================

async function 加载金融热点() {
    const 容器 = document.getElementById('特征容器');
    if (!容器) return;

    let 金融数据 = null;
    try {
        const 响应 = await fetch('金融API.json?v=' + Date.now());
        if (响应.ok) 金融数据 = await 响应.json();
    } catch (e) { console.log('金融API加载失败：' + e.message); }

    if (!金融数据 || !金融数据.articles || 金融数据.articles.length === 0) {
        const 标题 = document.createElement('div'); 标题.className = '特征区标题'; 标题.textContent = '金融热点';
        容器.appendChild(标题);
        const 空 = document.createElement('div'); 空.className = '空状态';
        空.innerHTML = '<p>金融热点数据加载中，请稍后刷新</p>';
        容器.appendChild(空);
        return;
    }

    const 标题 = document.createElement('div'); 标题.className = '特征区标题';
    标题.textContent = '金融热点 · ' + 金融数据.updated.substring(0, 10);
    容器.appendChild(标题);

    // 与其他栏目一致：1 张主视觉卡片 + 3 张次卡片
    const 头条 = 金融数据.articles.slice(0, 4);
    const 其余 = 金融数据.articles.slice(4);

    if (头条.length > 0) {
        const 网格 = document.createElement('div'); 网格.className = '特征网格';
        头条.forEach((a, index) => {
            const 卡片 = document.createElement('article'); 卡片.className = '特征卡片';
            if (index === 0) {
                卡片.classList.add('主推荐卡片');
            } else 卡片.classList.add('次推荐卡片');
            卡片.dataset.index = String(index + 1).padStart(2, '0');
            卡片.tabIndex = 0; 卡片.setAttribute('role', 'link');
            卡片.onclick = () => 打开文章详情(a);
            卡片.onkeydown = e => { if (e.key === 'Enter') 卡片.click(); };
            卡片.innerHTML = `
                <div class="卡片元信息"><span class="卡片来源">${转义HTML(a.来源||'')}</span><span class="卡片日期">${转义HTML(a.日期||'')}</span></div>
                <div class="卡片标题">${转义HTML(a.标题||'')}</div>
                <div class="卡片摘要">${转义HTML((a.摘要||'').substring(0, 100))}</div>
                ${a.标签 ? '<div class="卡片标签栏">' + a.标签.slice(0,3).map(t => `<span class="卡片标签">${转义HTML(t)}</span>`).join('') + '</div>' : ''}`;
            if (index === 0) 应用卡片主视觉(卡片, a, '金融', 金融数据.主视觉 || 金融数据.封面 || '', index);
            网格.appendChild(卡片);
        });
        容器.appendChild(网格);
    }

    if (其余.length > 0) {
        const 列表容器 = document.getElementById('列表容器');
        if (列表容器) {
            const 列表标题 = document.createElement('div'); 列表标题.className = '列表区域标题'; 列表标题.textContent = '更多热点';
            列表容器.appendChild(列表标题);
            const 列表 = document.createElement('ul'); 列表.className = '资讯列表';
            其余.forEach(a => {
                const 项 = document.createElement('li'); 项.className = '资讯列表项';
                项.innerHTML = `<a class="资讯列表链接" href="${a.链接||'#'}" target="_blank" rel="noopener"><div class="列表元信息"><span class="列表来源">${a.来源||''}</span><span class="列表分隔">·</span><span class="列表日期">${a.日期||''}</span></div><span class="列表标题">${a.标题||''}</span></a>`;
                列表.appendChild(项);
            });
            列表容器.appendChild(列表);
        }
    }
}

// ============================================================
// 行业热议
// ============================================================

async function 加载行业热议() {
    const 容器 = document.getElementById('特征容器');
    if (!容器) return;

    let 数据 = null;
    try {
        const 响应 = await fetch('https://boke.jgyq.me/industry-buzz.json?v=' + Date.now());
        if (响应.ok) 数据 = await 响应.json();
    } catch (e) {
        try {
            const 响应 = await fetch('industry-buzz.json?v=' + Date.now());
            if (响应.ok) 数据 = await 响应.json();
        } catch (e2) {}
    }

    if (!数据 || !数据.articles || 数据.articles.length === 0) {
        容器.innerHTML = '<div class="特征区标题">行业热议</div><div class="空状态"><p>暂无数据</p></div>';
        return;
    }

    const 标题 = document.createElement('div'); 标题.className = '特征区标题'; 标题.textContent = '行业热议 · 商业八卦实时追踪';
    容器.appendChild(标题);

    const 列表 = document.createElement('ul'); 列表.className = '一手列表';
    const 限制数 = 5;
    数据.articles.forEach((a, i) => {
        const 项 = document.createElement('li'); 项.className = '一手列表项';
        if (i >= 限制数) 项.style.display = 'none';
        const cat = a.分类 || '';
        const 有原文 = !!a.原文;
        let tagHTML;
        if (有原文) {
            tagHTML = `<span class="一手标记" style="border-color:rgba(217,109,66,0.4);color:var(--signal)">外媒</span>`;
        } else if (cat) {
            tagHTML = `<span class="一手标记" style="border-color:rgba(84,184,138,0.3);color:var(--aurora-green)">${cat}</span>`;
        } else {
            tagHTML = '<span class="一手标记">热议</span>';
        }
        let titleHTML;
        if (有原文) {
            titleHTML = `<span class="一手标题文字">${a.标题}<br><span style="font-size:13px;color:var(--text-faint);font-weight:400">${a.原文}</span></span>`;
        } else {
            titleHTML = `<span class="一手标题文字">${a.标题}</span>`;
        }
        项.innerHTML = `<a class="一手列表链接" href="${a.链接||'#'}" target="_blank" rel="noopener">${tagHTML}<span class="一手来源">${a.来源||''}</span><span class="一手日期">${a.日期||''}</span>${titleHTML}</a>`;
        列表.appendChild(项);
    });
    容器.appendChild(列表);
    // 收起/展开
    if (数据.articles.length > 限制数) {
        const 折叠按钮 = document.createElement('button');
        折叠按钮.className = '加载更多按钮';
        折叠按钮.style.marginTop = '12px';
        const 多余 = 列表.children.length - 限制数;
        折叠按钮.textContent = `展开全部（${多余} 条）`;
        let 已展开 = false;
        折叠按钮.onclick = () => {
            已展开 = !已展开;
            for (let i = 限制数; i < 列表.children.length; i++) {
                列表.children[i].style.display = 已展开 ? '' : 'none';
            }
            折叠按钮.textContent = 已展开 ? '收起' : `展开全部（${多余} 条）`;
        };
        容器.appendChild(折叠按钮);
    }
}

// ============================================================
// GitHub 工具排行
// ============================================================

async function 加载工具排行() {
    const 容器 = document.getElementById('工具容器');
    if (!容器) return;

    let 数据 = { stable: [], trending: [] };
    try {
        const 响应 = await fetch('GitHub工具排行.json?v=' + Date.now());
        if (响应.ok) {
            const raw = await 响应.json();
            // 新版：{stable, trending} | 旧版平铺数组兼容
            if (raw.stable && raw.trending !== undefined) {
                数据 = raw;
            } else if (Array.isArray(raw)) {
                数据.stable = raw;
            }
        }
    } catch (e) { console.log('工具排行加载失败：' + e.message); }

    if (数据.stable.length === 0 && 数据.trending.length === 0) return;

    // 核心仓库
    if (数据.stable.length > 0) {
        const 标题 = document.createElement('div'); 标题.className = '工具标题'; 标题.textContent = '核心工具追踪';
        容器.appendChild(标题);
        const 列表 = document.createElement('ul'); 列表.className = '工具列表';
        数据.stable.forEach(工具 => {
            const 项 = document.createElement('li'); 项.className = '工具列表项';
            const 变化标签 = 工具.本周变化 && 工具.本周变化 !== '─' ?
                `<span class="工具排行标记" style="color:var(--aurora-green)">${工具.本周变化}</span>` :
                `<span class="工具排行标记">${工具.星标 || ''}</span>`;
            项.innerHTML = `
                <span class="工具名">${工具.名称 || ''}<a class="工具链接" href="https://github.com/${工具.repo}" target="_blank" rel="noopener">&nearr;</a></span>
                <span class="工具说明">${工具.说明 || ''}</span>
                ${变化标签}`;
            列表.appendChild(项);
        });
        容器.appendChild(列表);
    }

    // 本周趋势
    if (数据.trending.length > 0) {
        const 标题2 = document.createElement('div'); 标题2.className = '工具标题'; 标题2.textContent = '本周趋势项目';
        容器.appendChild(标题2);
        const 列表2 = document.createElement('ul'); 列表2.className = '工具列表';
        数据.trending.forEach(工具 => {
            const 项 = document.createElement('li'); 项.className = '工具列表项';
            项.innerHTML = `
                <span class="工具名">${工具.名称 || ''}<a class="工具链接" href="https://github.com/${工具.repo}" target="_blank" rel="noopener">&nearr;</a></span>
                <span class="工具说明">${工具.说明 || ''}</span>
                <span class="工具排行标记">${工具.星标 || ''} stars</span>`;
            列表2.appendChild(项);
        });
        容器.appendChild(列表2);
    }
}

// ============================================================
// 平台热点聚合
// ============================================================

async function 加载平台热点() {
    const 标签组 = document.getElementById('平台标签组');
    const 内容区 = document.getElementById('平台内容');
    if (!标签组 || !内容区) return;

    标签组.innerHTML = '';
    内容区.innerHTML = '<div class="平台空状态"><p>加载中...</p></div>';

    let 数据 = null;
    const urls = [
        'https://boke.jgyq.me/platform-hot.json?v=' + Date.now(),
        'platform-hot.json?v=' + Date.now(),
        'https://raw.githubusercontent.com/t416454999/George/main/platform-hot.json?v=' + Date.now(),
    ];
    for (const url of urls) {
        try {
            const 控制器 = new AbortController();
            setTimeout(() => 控制器.abort(), 15000);
            const 响应 = await fetch(url, { signal: 控制器.signal });
            if (响应.ok) { 数据 = await 响应.json(); break; }
            else console.warn('平台热点 fetch 失败:', url, 响应.status);
        } catch (e) { console.warn('平台热点 fetch 异常:', url, e.message); }
    }

    if (!数据 || !数据.platforms) {
        内容区.innerHTML = '<div class="平台空状态"><p>暂无数据，请稍后刷新</p></div>';
        return;
    }

    const 平台名列表 = Object.keys(数据.platforms).filter(k => 数据.platforms[k].length > 0);
    if (平台名列表.length === 0) {
        内容区.innerHTML = '<div class="平台空状态"><p>暂无数据，请稍后刷新</p></div>';
        return;
    }

    // 上次选中的平台
    let 当前平台 = localStorage.getItem('平台热点选中') || 平台名列表[0];
    if (!平台名列表.includes(当前平台)) 当前平台 = 平台名列表[0];

    // 渲染标签
    平台名列表.forEach(名 => {
        const 标签 = document.createElement('button');
        标签.className = '平台标签' + (名 === 当前平台 ? ' 活跃' : '');
        标签.textContent = 名;
        标签.onclick = () => {
            document.querySelectorAll('.平台标签').forEach(t => t.classList.remove('活跃'));
            标签.classList.add('活跃');
            localStorage.setItem('平台热点选中', 名);
            渲染平台列表(内容区, 数据.platforms[名]);
        };
        标签组.appendChild(标签);
    });

    // 渲染当前平台
    渲染平台列表(内容区, 数据.platforms[当前平台]);
}

function 渲染平台列表(容器, 文章列表) {
    容器.innerHTML = '';
    if (!文章列表 || 文章列表.length === 0) {
        容器.innerHTML = '<div class="平台空状态"><p>暂无数据</p></div>';
        return;
    }

    文章列表.forEach((a, i) => {
        const 条目 = document.createElement('a');
        条目.className = '热点条目';
        条目.href = a.link || '#';
        条目.target = '_blank';
        条目.rel = 'noopener';
        条目.innerHTML = `
            <span class="热点排名">${a.rank || i + 1}</span>
            <span class="热点标题">${a.title || ''}</span>
            ${a.heat ? '<span class="热点热度">' + a.heat + '</span>' : ''}
        `;
        容器.appendChild(条目);
    });
}

// ============================================================
// 筛选 / 搜索 / 详情 / 移动菜单
// ============================================================

function 筛选分类(分类名) {
    状态.当前分类 = 分类名;
    document.querySelectorAll('.分类标签').forEach(tag => {
        const t = tag.textContent.trim();
        tag.classList.toggle('活跃', t === 分类名 || (分类名 === '全部' && t === '全部'));
    });
    切换页面('首页', true); // true = 不滚动到顶部
}
function 切换排序(方式) { 状态.排序方式 = 方式; 应用筛选(); }

function 初始化搜索() { const 输入框 = document.getElementById('搜索输入框'); if (输入框) 输入框.value = 状态.搜索关键词; if (状态.搜索关键词) 执行搜索(); }
function 实时搜索() { clearTimeout(window.搜索定时器); window.搜索定时器 = setTimeout(() => 执行搜索(), 400); }
function 快速搜索(关键词) { const 输入框 = document.getElementById('搜索输入框'); if (输入框) 输入框.value = 关键词; 状态.搜索关键词 = 关键词; 执行搜索(); }

function 执行搜索() {
    const 输入框 = document.getElementById('搜索输入框');
    const 关键词 = 输入框 ? 输入框.value.trim() : ''; 状态.搜索关键词 = 关键词;
    const 结果容器 = document.getElementById('搜索结果');
    if (!结果容器) return;
    if (!关键词) { 结果容器.innerHTML = '<p class="搜索提示">输入关键词开始搜索</p>'; return; }
    const 结果 = 状态.文章列表.filter(a => `${a.标题} ${a.摘要} ${a.内容} ${a.来源} ${(a.标签||[]).join(' ')}`.toLowerCase().includes(关键词.toLowerCase()));
    if (结果.length === 0) { 结果容器.innerHTML = `<div class="空状态"><p>未找到与「${关键词}」相关的资讯</p></div>`; return; }
    结果容器.innerHTML = `<p style="margin-bottom:24px;color:var(--text-faint);font-size:13px">找到 <span style="color:var(--signal);font-weight:600">${结果.length}</span> 篇</p>`;
    const 列表 = document.createElement('ul'); 列表.className = '资讯列表';
    结果.slice(0,30).forEach(a => {
        const 项 = document.createElement('li'); 项.className = '资讯列表项';
        项.innerHTML = `<a class="资讯列表链接" href="#详情/${a.id}" onclick="event.preventDefault();打开文章详情ById(${a.id})"><div class="列表元信息"><span class="列表来源">${a.来源||''}</span><span class="列表分隔">·</span><span class="列表日期">${a.日期||''}</span></div><span class="列表标题">${高亮关键词(a.标题,关键词)}</span><span class="列表分类">${a.分类||''}</span></a>`;
        列表.appendChild(项);
    });
    结果容器.appendChild(列表);
}

function 高亮关键词(文本, 关键词) {
    if (!文本 || !关键词) return 文本 || '';
    const 转义 = 关键词.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return 文本.replace(new RegExp(`(${转义})`, 'gi'), '<mark>$1</mark>');
}

function 打开文章详情(文章) { if (!文章||!文章.id) return; 状态.当前文章ID=文章.id; 状态.当前详情文章=文章; 状态.当前页面='详情'; history.pushState(null,'','#详情/'+文章.id); 显示文章详情(); }
function 打开文章详情ById(id) { const 文章=状态.文章列表.find(a=>a.id===id); if(文章) 打开文章详情(文章); }

function 显示文章详情() {
    const 专题文章 = Object.values(状态.专题缓存).flatMap(数据 => Array.isArray(数据.articles) ? 数据.articles : []);
    const 文章 = (状态.当前详情文章 && 状态.当前详情文章.id === 状态.当前文章ID ? 状态.当前详情文章 : null)
        || 状态.文章列表.find(a=>a.id===状态.当前文章ID)
        || 专题文章.find(a=>a.id===状态.当前文章ID);
    if(!文章){切换页面('首页');return;}
    document.querySelectorAll('.页面视图').forEach(v=>v.classList.remove('活跃视图'));
    document.querySelectorAll('.导航链接').forEach(l=>l.classList.remove('活跃'));
    const dv=document.getElementById('详情视图'); if(dv)dv.classList.add('活跃视图');
    const c=document.getElementById('详情容器'); if(!c)return;
    const 正文文本 = 文章.正文 || 文章.内容 || 文章.摘要 || '暂无详细内容。';
    const 段落 = 正文文本.split('\n').filter(p=>p.trim()).map(p => {
        const 行 = p.trim(); const 标题匹配 = 行.match(/^(#{1,3})\s+(.+)/);
        if (标题匹配) { const 标签 = 标题匹配[1].length === 1 ? 'h2' : 'h3'; return `<${标签}>${转义HTML(标题匹配[2])}</${标签}>`; }
        return `<p>${转义HTML(行)}</p>`;
    }).join('');
    const 要点 = Array.isArray(文章.要点) && 文章.要点.length
        ? `<section class="详情要点"><h2>阅读要点</h2><ul>${文章.要点.map(点 => `<li>${转义HTML(点)}</li>`).join('')}</ul></section>` : '';
    const 导语 = 文章.导语 ? `<p class="详情导语">${转义HTML(文章.导语)}</p>` : '';
    const 封面 = 安全外链(文章.封面 || 文章.图片);
    const 封面HTML = 封面 ? `<figure class="详情封面"><img src="${转义HTML(封面)}" alt="${转义HTML(文章.标题 || '')}" decoding="async" fetchpriority="high"></figure>` : '';
    const 原文 = 安全外链(文章.原文链接 || 文章.链接);
    const 出处 = 文章.出处说明 || 文章.版权 || (文章.来源 ? '内容整理自 ' + 文章.来源 + '，版权归原作者及原机构所有。' : '');
    const 出处HTML = 出处 || 原文 ? `<aside class="详情出处"><strong>出处说明</strong><p>${转义HTML(出处)}</p>${原文 ? `<a href="${转义HTML(原文)}" target="_blank" rel="noopener" class="详情来源链接">查看原始出处</a>` : ''}</aside>` : '';
    c.innerHTML=`<button class="详情返回" onclick="切换页面('首页')">&larr; 返回</button>${封面HTML}<h1 class="详情标题">${转义HTML(文章.标题||'')}</h1><div class="详情元信息"><span>来源：${转义HTML(文章.来源||'')}</span><span>${转义HTML(文章.日期||'')}</span><span>分类：${转义HTML(文章.分类||'')}</span>${文章.热度?'<span>热度 '+转义HTML(文章.热度)+'</span>':''}</div>${导语}${要点}<div class="详情正文">${段落}</div>${出处HTML}`;
    window.scrollTo({top:0,behavior:'smooth'});
}

function 切换移动菜单() { document.getElementById('导航菜单').classList.toggle('展开'); document.querySelector('.菜单按钮').classList.toggle('展开'); }
function 监听滚动() {
    const 返回按钮=document.getElementById('返回顶部');
    window.addEventListener('scroll',()=>{
        if(返回按钮) 返回按钮.classList.toggle('可见',window.scrollY>600);
    });
}
function 滚动到顶部(){window.scrollTo({top:0,behavior:'smooth'});}

window.addEventListener('popstate',()=>{
    const hash=window.location.hash.slice(1);
    if(hash.startsWith('详情/')){const id=parseInt(hash.split('详情/')[1]);if(id){状态.当前文章ID=id;状态.当前页面='详情';显示文章详情();return;}}
    if(hash&&['首页','分类','搜索','关于'].includes(hash))切换页面(hash);else 切换页面('首页');
});
