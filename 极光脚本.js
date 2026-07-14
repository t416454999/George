/* ============================================================
   极光引擎 · 前端脚本
   布局：4等大卡片(2x2) → 一手消息(文字行) → 更多资讯(文字行) → GitHub工具
   最后修改：见 修改登记.json
   ============================================================ */

const 状态 = {
    当前页面: '首页', 当前分类: '全部', 排序方式: '最新',
    搜索关键词: '', 文章列表: [], 首页精选文章: [], 首页头条ID: null, 已筛选文章: [],
    来源集合: new Set(), 当前文章ID: null, 当前详情文章: null, 专题缓存: {},
    专题请求序号: 0, 专题请求控制器: null, 金融缓存: null, 搜索扩展文章: [], 搜索扩展加载任务: null,
    编辑评分索引: {},  // { "国际形势": [{id, 编辑分, ...}, ...], ... }
};

// 跟随当前脚本的发布版本。版本只在发布时变化，避免每次访问都强制绕过浏览器缓存。
const 数据资源版本 = (() => {
    try { return new URL(document.currentScript.src).searchParams.get('v') || '20260714i'; }
    catch { return '20260714i'; }
})();

const 专题栏目文件 = {
    '国际形势': '国际形势.json',
    '世界杯': '世界杯.json',
    '人文艺术': '人文艺术.json',
    '情感': '情感.json',
};

function 数据资源地址(路径) {
    return 路径 + (String(路径).includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(数据资源版本);
}

async function 获取JSON(路径, 选项 = {}) {
    const 响应 = await fetch(数据资源地址(路径), 选项);
    if (!响应.ok) throw new Error('HTTP ' + 响应.status);
    return 响应.json();
}

document.addEventListener('DOMContentLoaded', async () => {
    await 初始化数据();
    初始化路由();
    监听滚动();
    初始化分类折叠();
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
        const 响应 = await fetch(数据资源地址('文章数据库.json'));
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

    try {
        const 精选响应 = await fetch(数据资源地址('首页精选.json'));
        if (精选响应.ok) {
            const 精选数据 = await 精选响应.json();
            状态.首页精选文章 = Array.isArray(精选数据.articles) ? 精选数据.articles : [];
            状态.首页头条ID = 精选数据.headline_id || null;
        }
    } catch (错误) {
        console.warn('首页精选加载异常，使用文章库回退：' + 错误.message);
    }

    try {
        const 评分响应 = await fetch(数据资源地址('编辑评分索引.json'));
        if (评分响应.ok) {
            const 评分数据 = await 评分响应.json();
            状态.编辑评分索引 = 评分数据.sections || {};
        }
    } catch (错误) {
        // 编辑评分索引是渐进功能，没有也不影响运行
        console.log('编辑评分索引未加载，使用前端质量分回退');
    }

    [...状态.文章列表, ...状态.首页精选文章].forEach(文章 => { 状态.来源集合.add(文章.来源); });
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

function 安全解码(值) {
    try { return decodeURIComponent(值); } catch { return 值; }
}

function 解析路由(rawHash = window.location.hash.slice(1)) {
    const 分段 = String(rawHash || '').split('/').map(安全解码);
    if (分段[0] === '详情') {
        const 有分类 = 分段.length >= 3;
        const id = String(有分类 ? 分段.slice(2).join('/') : (分段[1] || '')).trim();
        return { 类型: '详情', 分类: 有分类 ? 分段[1] : '', id: id || null };
    }
    return { 类型: '页面', 页面: 安全解码(String(rawHash || '')) };
}

async function 处理当前路由() {
    const 路由 = 解析路由();
    if (路由.类型 === '详情') {
        状态.当前文章ID = 路由.id;
        状态.当前页面 = '详情';
        await 显示文章详情(路由.分类);
        return;
    }
    if (路由.页面 && ['首页','分类','搜索','关于'].includes(路由.页面)) 切换页面(路由.页面);
    else 切换页面('首页');
}

async function 初始化路由() {
    await 处理当前路由();
    window.addEventListener('hashchange', 处理当前路由);
}

function 切换页面(页面名) {
    状态.当前页面 = 页面名; 状态.当前文章ID = null;
    document.querySelectorAll('.页面视图').forEach(v => v.classList.remove('活跃视图'));
    const 视图映射 = { '首页':'首页视图','分类':'分类视图','搜索':'搜索视图','关于':'关于视图' };
    const 视图ID = 视图映射[页面名];
    if (视图ID) { const 视图 = document.getElementById(视图ID); if (视图) 视图.classList.add('活跃视图'); }
    document.querySelectorAll('.导航链接').forEach(link => { link.classList.toggle('活跃', link.dataset.page === 页面名); });
    if (安全解码(window.location.hash.slice(1)) !== 页面名) history.pushState(null, '', '#' + encodeURIComponent(页面名));
    switch (页面名) { case '首页': 渲染首页(); break; case '分类': 加载平台热点(); break; case '搜索': 初始化搜索(); break; }
    const 菜单 = document.getElementById('导航菜单'); const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.remove('展开');
    if (按钮) { 按钮.classList.remove('展开'); 按钮.setAttribute('aria-expanded', 'false'); }
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

    let 文章列表 = 状态.当前分类 === '全部' && 状态.首页精选文章.length
        ? [...状态.首页精选文章]
        : [...状态.文章列表];
    if (状态.当前分类 === '全部' && 状态.首页精选文章.length > 0 && 文章列表.length < 50) {
        const 已有IDs = new Set(文章列表.map(a => String(a.id)));
        const 补充 = 状态.文章列表.filter(a => !已有IDs.has(String(a.id)));
        文章列表 = 文章列表.concat(补充.slice(0, 50 - 文章列表.length));
    }
    if (状态.当前分类 !== '全部') 文章列表 = 文章列表.filter(a => a.分类 === 状态.当前分类 || (状态.当前分类 === 'AI应用' && a.分类 === 'AI绘画'));
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
        const 原值 = String(值 == null ? '' : 值).trim();
        if (!原值 || 原值 === '#') return '';
        const u = new URL(原值, window.location.href);
        return ['http:', 'https:'].includes(u.protocol) ? u.href : '';
    } catch { return ''; }
}

function 获取文章图片(文章, 备用图片 = '') {
    const 候选 = [文章 && 文章.图片, 文章 && 文章.原始图片, 文章 && 文章.原图, 文章 && 文章.封面, 备用图片]
        .filter(Boolean);
    const 真实图片 = 候选.find(值 => !/assets\/covers\//i.test(String(值)));
    return 安全外链(真实图片 || 候选[0] || '');
}

function 获取原标题(文章) {
    const 原标题 = String((文章 && 文章.原标题) || '').replace(/【[^】]+】/g, '').trim();
    return 原标题 && 原标题 !== String((文章 && 文章.标题) || '').trim() ? 原标题 : '';
}

/** 文章质量评分：用于专题板块排序，决定哪些文章进入特征区（含图片） */
function 计算文章质量分(文章, 分类名) {
    let 分 = 0;
    // 1. 主编评分（最高权重）——已存在于首页精选的跨板块评分
    if (文章.编辑分 != null) 分 += Math.round(文章.编辑分 * 1.5);
    // 2. 真实配图（非占位封面）：直接检查文章原始图片字段
    const 原始图片字段 = 文章 && (文章.图片 || 文章.原始图片 || 文章.封面 || '');
    if (原始图片字段 && !/assets\/covers\//i.test(原始图片字段)) 分 += 40;
    // 3. 内容完整度
    if (文章.导语) 分 += 20;
    if (Array.isArray(文章.要点) && 文章.要点.length) 分 += 15;
    if ((文章.摘要 || '').length > 80) 分 += 10;
    // 4. 来源质量
    if (文章.来源级别 === 'A') 分 += 20;
    else if (文章.来源级别 === 'B') 分 += 10;
    // 5. 时效
    if (文章.日期) {
        try {
            const d = new Date(文章.日期);
            if (!isNaN(d.getTime())) {
                const 天数 = (Date.now() - d.getTime()) / 86400000;
                if (天数 <= 1) 分 += 25;
                else if (天数 <= 3) 分 += 15;
                else if (天数 <= 7) 分 += 8;
            }
        } catch {}
    }
    return 分;
}

function 添加文本元素(父元素, 标签, 类名, 文本) {
    const 元素 = document.createElement(标签);
    if (类名) 元素.className = 类名;
    元素.textContent = 文本 || '';
    父元素.appendChild(元素);
    return 元素;
}

function 构建详情Hash(文章) {
    const 分类 = String((文章 && 文章.分类) || '').trim();
    return '#详情/' + (分类 ? encodeURIComponent(分类) + '/' : '') + encodeURIComponent(String(文章.id));
}

function GitHub仓库链接(repo) {
    const 值 = String(repo || '').trim();
    return /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(值) ? 'https://github.com/' + 值 : '';
}

async function 获取专题数据(分类名, 选项 = {}) {
    if (状态.专题缓存[分类名]) return 状态.专题缓存[分类名];
    const 数据 = await 获取JSON(专题栏目文件[分类名], 选项);
    状态.专题缓存[分类名] = 数据;
    return 数据;
}

async function 获取金融数据() {
    if (状态.金融缓存) return 状态.金融缓存;
    let 主文件错误 = null;
    for (const 文件 of ['金融API.json', '金融API-国外.json']) {
        try {
            const 数据 = await 获取JSON(文件);
            if (数据 && Array.isArray(数据.articles) && 数据.articles.length > 0) {
                数据.articles.forEach(文章 => { if (!文章.分类) 文章.分类 = '金融'; });
                状态.金融缓存 = 数据;
                if (文件 !== '金融API.json') console.info('金融API.json 不可用，已回退到金融API-国外.json');
                return 数据;
            }
        } catch (错误) {
            if (!主文件错误) 主文件错误 = 错误;
        }
    }
    throw (主文件错误 || new Error('金融数据格式无效'));
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
            数据 = await 获取专题数据(分类名, { signal: 请求控制器.signal });
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

    // 主编打分排序：高分前4 → 特征卡片（含图片），其余 → 更多内容（纯文本）
    const 栏目评分 = 状态.编辑评分索引[分类名] || [];
    const 评分查找 = {};
    栏目评分.forEach(s => { if (s.编辑分 != null) 评分查找[String(s.id)] = s.编辑分; });
    文章.sort((a, b) => {
        const 分A = 评分查找[String(a.id)] || 计算文章质量分(a, 分类名);
        const 分B = 评分查找[String(b.id)] || 计算文章质量分(b, 分类名);
        return 分B - 分A;
    });

    const 网格 = document.createElement('div');
    网格.className = '特征网格 专题网格 分类专题-' + String(分类名 || '').replace(/[^\u4e00-\u9fa5A-Za-z0-9_-]/g, '');
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
    const 图片 = 获取文章图片(文章, 备用图片);
    卡片.classList.add('有主视觉', '分类主视觉-' + String(分类名 || '全部').replace(/[^\u4e00-\u9fa5A-Za-z0-9_-]/g, ''));
    // 情感数据没有真实配图时保留纯色杂志版，避免把通用占位图误当成内容图片。
    if (!图片 || (分类名 === '情感' && /assets\/covers\/emotion\.svg(?:[?#].*)?$/i.test(图片))) return;
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
    卡片.setAttribute('aria-label', '阅读：' + (文章.标题 || '无标题'));
    卡片.onclick = () => 打开文章详情(文章);
    卡片.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); 卡片.click(); } };
    const 候选图片 = index === 0 ? '' : 获取文章图片(文章);
    const 图片 = 分类名 === '情感' && /assets\/covers\/emotion\.svg(?:[?#].*)?$/i.test(候选图片) ? '' : 候选图片;
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
    const 原标题 = 分类名 === '人文艺术' ? 获取原标题(文章) : '';
    if (原标题) 添加文本元素(卡片, 'div', '卡片原标题', 原标题);
    添加文本元素(卡片, 'div', '卡片摘要', (文章.摘要 || '').substring(0, 180));
    if (文章.版权) 添加文本元素(卡片, 'div', '专题版权', 文章.版权);
    if (文章.编辑分 != null) {
        const 说明 = document.createElement('div');
        说明.className = '编辑推荐说明';
        说明.textContent = `${文章.来源级别 || ''}级来源 · 编辑分 ${文章.编辑分} · ${文章.入选理由 || '编辑推荐'}`;
        卡片.appendChild(说明);
    }
    return 卡片;
}

function 创建专题列表项(文章) {
    const 项 = document.createElement('li'); 项.className = '资讯列表项';
    const 链接 = document.createElement('a'); 链接.className = '资讯列表链接';
    链接.href = 构建详情Hash(文章);
    链接.onclick = e => { e.preventDefault(); 打开文章详情(文章); };
    const 元信息 = document.createElement('div'); 元信息.className = '列表元信息';
    添加文本元素(元信息, 'span', '列表来源', 文章.来源 || '');
    添加文本元素(元信息, 'span', '列表分隔', '·');
    添加文本元素(元信息, 'span', '列表日期', 文章.日期 || '');
    链接.appendChild(元信息);
    const 标题组 = document.createElement('span'); 标题组.className = '列表标题';
    添加文本元素(标题组, 'span', '列表中文标题', 文章.标题 || '');
    const 原标题 = 文章.分类 === '人文艺术' ? 获取原标题(文章) : '';
    if (原标题) 添加文本元素(标题组, 'span', '列表原标题', 原标题);
    链接.appendChild(标题组);
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
            标题.textContent = 分类 === '全部'
                ? (状态.首页头条ID ? '今日头条 · 编辑精选' : '今日推荐 · 本期无人达到头条门槛')
                : 分类;
            容器.appendChild(标题);
            const 网格 = document.createElement('div'); 网格.className = '特征网格';
            特征文章.forEach((文章, index) => {
                const 卡片 = 创建特征卡片(文章, 分类, 文章.主视觉 || 文章.封面 || '', index);
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
    链接.href=构建详情Hash(文章); 链接.onclick=(e)=>{e.preventDefault();打开文章详情(文章);};
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

function append列表项(列表, 文章) { 列表.appendChild(createListLink(文章)); }

function 创建一手行(文章, 列表) {
    const 项 = document.createElement('li'); 项.className = '一手列表项';
    const 链接 = document.createElement('a'); 链接.className = '一手列表链接';
    链接.href=构建详情Hash(文章); 链接.onclick=(e)=>{e.preventDefault();打开文章详情(文章);};
    添加文本元素(链接, 'span', '一手标记', '一手');
    添加文本元素(链接, 'span', '一手来源', 文章.来源 || '');
    添加文本元素(链接, 'span', '一手日期', 文章.日期 || '');
    添加文本元素(链接, 'span', '一手标题文字', 文章.标题 || '');
    if (文章.原标题) 添加文本元素(链接, 'span', '一手原标题', String(文章.原标题).replace(/【[^】]+】/g,'').trim());
    if (文章.中文提炼) 添加文本元素(链接, 'span', '一手要点', 文章.中文提炼);
    项.appendChild(链接); 列表.appendChild(项);
}

function 渲染特征区(文章列表) { /* 已合并到渲染容器 */ }

function 创建特征卡片(文章, 分类名 = '', 备用图片 = '', index = -1) {
    const 卡片 = document.createElement('article'); 卡片.className = '特征卡片';
    卡片.tabIndex = 0; 卡片.setAttribute('role', 'link');
    卡片.setAttribute('aria-label', '阅读：' + (文章.标题 || '无标题'));
    卡片.onclick = () => 打开文章详情(文章);
    卡片.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); 卡片.click(); } };
    // 如果文章有真实配图，次卡片显示图片（主卡片由应用卡片主视觉处理）
    if (index !== 0) {
        const 候选图片 = 获取文章图片(文章);
        if (候选图片 && !/assets\/covers\//i.test(候选图片)) {
            卡片.classList.add('有图片');
            const 图框 = document.createElement('div'); 图框.className = '专题图片框';
            const img = document.createElement('img'); img.src = 候选图片; img.alt = 文章.标题 || '';
            img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
            img.onerror = () => { 图框.remove(); 卡片.classList.remove('有图片'); };
            图框.appendChild(img); 卡片.prepend(图框);
        }
    }
    const 元信息 = document.createElement('div'); 元信息.className = '卡片元信息';
    添加文本元素(元信息, 'span', '卡片来源', 文章.来源 || '');
    添加文本元素(元信息, 'span', '卡片日期', 文章.日期 || '');
    添加文本元素(元信息, 'span', '卡片分类', 文章.分类 || '');
    卡片.appendChild(元信息);
    添加文本元素(卡片, 'div', '卡片标题', 文章.标题 || '无标题');
    添加文本元素(卡片, 'div', '卡片摘要', String(文章.摘要 || '').substring(0,120));
    const 标签 = Array.isArray(文章.标签) ? 文章.标签.slice(0, 3) : [];
    if (标签.length) {
        const 标签栏 = document.createElement('div'); 标签栏.className = '卡片标签栏';
        标签.forEach(标签名 => 添加文本元素(标签栏, 'span', '卡片标签', 标签名));
        卡片.appendChild(标签栏);
    }
    if (文章.编辑分 != null) {
        const 说明 = document.createElement('div');
        说明.className = '编辑推荐说明';
        说明.textContent = `${文章.来源级别 || ''}级来源 · 编辑分 ${文章.编辑分} · ${文章.入选理由 || ''}`;
        卡片.appendChild(说明);
    }
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
        金融数据 = await 获取金融数据();
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
            卡片.setAttribute('aria-label', '阅读：' + (a.标题 || '无标题'));
            卡片.onclick = () => 打开文章详情(a);
            卡片.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); 卡片.click(); } };
            卡片.innerHTML = `
                <div class="卡片元信息"><span class="卡片来源">${转义HTML(a.来源||'')}</span><span class="卡片日期">${转义HTML(a.日期||'')}</span></div>
                <div class="卡片标题">${转义HTML(a.标题||'')}</div>
                <div class="卡片摘要">${转义HTML((a.摘要||'').substring(0, 100))}</div>
                ${a.标签 ? '<div class="卡片标签栏">' + a.标签.slice(0,3).map(t => `<span class="卡片标签">${转义HTML(t)}</span>`).join('') + '</div>' : ''}`;
            if (index === 0) 应用卡片主视觉(卡片, a, '金融', 金融数据.主视觉 || 金融数据.封面 || '', index);
            else {
                const 金融图片 = 获取文章图片(a);
                if (金融图片 && !/assets\/covers\//i.test(金融图片)) {
                    卡片.classList.add('有图片');
                    const 图框 = document.createElement('div'); 图框.className = '专题图片框';
                    const img = document.createElement('img'); img.src = 金融图片; img.alt = a.标题 || '';
                    img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
                    img.onerror = () => { 图框.remove(); 卡片.classList.remove('有图片'); };
                    图框.appendChild(img); 卡片.prepend(图框);
                }
            }
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
            const 限制数 = 8;
            const allItems = 其余.map(a => createListLink(a));
            const limited = allItems.slice(0, 限制数);
            const rest = allItems.slice(限制数);
            limited.forEach(el => 列表.appendChild(el));
            列表容器.appendChild(列表);
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
                列表容器.appendChild(折叠按钮);
            }
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
        const 响应 = await fetch(数据资源地址('https://boke.jgyq.me/industry-buzz.json'));
        if (响应.ok) 数据 = await 响应.json();
    } catch (e) {
        try {
            const 响应 = await fetch(数据资源地址('industry-buzz.json'));
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
        const 链接 = document.createElement('a'); 链接.className = '一手列表链接';
        链接.href = 安全外链(a.链接) || '#'; 链接.target = '_blank'; 链接.rel = 'noopener noreferrer';
        const 标签 = document.createElement('span'); 标签.className = '一手标记';
        if (有原文) {
            标签.style.borderColor = 'rgba(217,109,66,0.4)'; 标签.style.color = 'var(--signal)'; 标签.textContent = '外媒';
        } else if (cat) {
            标签.style.borderColor = 'rgba(84,184,138,0.3)'; 标签.style.color = 'var(--aurora-green)'; 标签.textContent = cat;
        } else {
            标签.textContent = '热议';
        }
        链接.appendChild(标签);
        添加文本元素(链接, 'span', '一手来源', a.来源 || '');
        添加文本元素(链接, 'span', '一手日期', a.日期 || '');
        const 标题组 = 添加文本元素(链接, 'span', '一手标题文字', a.标题 || '');
        if (有原文) {
            标题组.appendChild(document.createElement('br'));
            const 原文 = 添加文本元素(标题组, 'span', '', a.原文);
            原文.style.fontSize = '13px'; 原文.style.color = 'var(--text-faint)'; 原文.style.fontWeight = '400';
        }
        项.appendChild(链接);
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
        const 响应 = await fetch(数据资源地址('GitHub工具排行.json'));
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
            const 名称 = 添加文本元素(项, 'span', '工具名', 工具.名称 || '');
            const 仓库链接 = GitHub仓库链接(工具.repo);
            if (仓库链接) {
                const 外链 = 添加文本元素(名称, 'a', '工具链接', '↗');
                外链.href = 仓库链接; 外链.target = '_blank'; 外链.rel = 'noopener noreferrer';
            }
            添加文本元素(项, 'span', '工具说明', 工具.说明 || '');
            const 变化标签 = 添加文本元素(项, 'span', '工具排行标记', 工具.本周变化 && 工具.本周变化 !== '─' ? 工具.本周变化 : (工具.星标 || ''));
            if (工具.本周变化 && 工具.本周变化 !== '─') 变化标签.style.color = 'var(--aurora-green)';
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
            const 名称 = 添加文本元素(项, 'span', '工具名', 工具.名称 || '');
            const 仓库链接 = GitHub仓库链接(工具.repo);
            if (仓库链接) {
                const 外链 = 添加文本元素(名称, 'a', '工具链接', '↗');
                外链.href = 仓库链接; 外链.target = '_blank'; 外链.rel = 'noopener noreferrer';
            }
            添加文本元素(项, 'span', '工具说明', 工具.说明 || '');
            添加文本元素(项, 'span', '工具排行标记', (工具.星标 || '') + ' stars');
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
        数据资源地址('platform-hot.json'),
        数据资源地址('https://boke.jgyq.me/platform-hot.json'),
        数据资源地址('https://raw.githubusercontent.com/t416454999/George/main/platform-hot.json'),
    ];
    for (const url of urls) {
        try {
            const 控制器 = new AbortController();
            const 定时器 = setTimeout(() => 控制器.abort(), 8000);
            const 响应 = await fetch(url, { signal: 控制器.signal }).finally(() => clearTimeout(定时器));
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
        条目.href = 安全外链(a.link) || '#';
        条目.target = '_blank';
        条目.rel = 'noopener noreferrer';
        添加文本元素(条目, 'span', '热点排名', a.rank || i + 1);
        添加文本元素(条目, 'span', '热点标题', a.title || '');
        if (a.heat) 添加文本元素(条目, 'span', '热点热度', a.heat);
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

async function 准备全站搜索数据() {
    if (!状态.搜索扩展加载任务) {
        状态.搜索扩展加载任务 = (async () => {
            const 结果 = await Promise.allSettled([
                ...Object.keys(专题栏目文件).map(分类 => 获取专题数据(分类)),
                获取金融数据(),
            ]);
            const 本次文章 = 结果
                .filter(项 => 项.status === 'fulfilled')
                .flatMap(项 => Array.isArray(项.value.articles) ? 项.value.articles : []);
            const 合并 = new Map(状态.搜索扩展文章.map(文章 => [`${文章.分类 || ''}/${文章.id || ''}/${文章.链接 || 文章.标题 || ''}`, 文章]));
            本次文章.forEach(文章 => 合并.set(`${文章.分类 || ''}/${文章.id || ''}/${文章.链接 || 文章.标题 || ''}`, 文章));
            状态.搜索扩展文章 = [...合并.values()];
            // 某个动态数据源本次失败时不永久缓存失败状态，下次搜索会只重试尚未进入各自缓存的数据源。
            if (结果.some(项 => 项.status === 'rejected')) 状态.搜索扩展加载任务 = null;
        })();
    }
    await 状态.搜索扩展加载任务;
}

function 添加高亮文本(父元素, 文本, 关键词) {
    const 内容 = String(文本 || '');
    const 查询 = String(关键词 || '');
    if (!查询) { 父元素.textContent = 内容; return; }
    const 小写内容 = 内容.toLocaleLowerCase();
    const 小写查询 = 查询.toLocaleLowerCase();
    let 起点 = 0;
    while (起点 < 内容.length) {
        const 命中 = 小写内容.indexOf(小写查询, 起点);
        if (命中 < 0) { 父元素.appendChild(document.createTextNode(内容.slice(起点))); break; }
        if (命中 > 起点) 父元素.appendChild(document.createTextNode(内容.slice(起点, 命中)));
        const 标记 = document.createElement('mark'); 标记.textContent = 内容.slice(命中, 命中 + 查询.length);
        父元素.appendChild(标记); 起点 = 命中 + 查询.length;
    }
}

async function 执行搜索() {
    const 输入框 = document.getElementById('搜索输入框');
    const 关键词 = 输入框 ? 输入框.value.trim() : ''; 状态.搜索关键词 = 关键词;
    const 结果容器 = document.getElementById('搜索结果');
    if (!结果容器) return;
    if (!关键词) { 结果容器.innerHTML = '<p class="搜索提示">输入关键词开始搜索</p>'; return; }
    结果容器.innerHTML = '<p class="搜索提示">正在搜索全站内容…</p>';
    await 准备全站搜索数据();
    if (状态.搜索关键词 !== 关键词) return;
    const 全部文章 = [...状态.文章列表, ...状态.首页精选文章, ...状态.搜索扩展文章];
    const 去重 = new Map();
    全部文章.forEach(a => 去重.set(`${a.分类 || ''}/${a.id || ''}/${a.链接 || a.标题 || ''}`, a));
    const 结果 = [...去重.values()].filter(a => `${a.标题 || ''} ${a.原标题 || ''} ${a.摘要 || ''} ${a.内容 || ''} ${a.正文 || ''} ${a.来源 || ''} ${(Array.isArray(a.标签) ? a.标签 : []).join(' ')}`.toLocaleLowerCase().includes(关键词.toLocaleLowerCase()));
    结果容器.innerHTML = '';
    if (结果.length === 0) {
        const 空 = document.createElement('div'); 空.className = '空状态';
        添加文本元素(空, 'p', '', `未找到与「${关键词}」相关的资讯`); 结果容器.appendChild(空); return;
    }
    const 统计 = document.createElement('p'); 统计.className = '搜索统计';
    统计.appendChild(document.createTextNode('找到 '));
    添加文本元素(统计, 'span', '', 结果.length);
    统计.appendChild(document.createTextNode(' 篇'));
    结果容器.appendChild(统计);
    const 列表 = document.createElement('ul'); 列表.className = '资讯列表';
    结果.slice(0,30).forEach(a => {
        const 项 = document.createElement('li'); 项.className = '资讯列表项';
        const 链接 = document.createElement('a'); 链接.className = '资讯列表链接'; 链接.href = 构建详情Hash(a);
        链接.onclick = e => { e.preventDefault(); 打开文章详情(a); };
        const 元信息 = document.createElement('div'); 元信息.className = '列表元信息';
        添加文本元素(元信息, 'span', '列表来源', a.来源 || '');
        添加文本元素(元信息, 'span', '列表分隔', '·');
        添加文本元素(元信息, 'span', '列表日期', a.日期 || ''); 链接.appendChild(元信息);
        const 标题 = document.createElement('span'); 标题.className = '列表标题'; 添加高亮文本(标题, a.标题, 关键词); 链接.appendChild(标题);
        添加文本元素(链接, 'span', '列表分类', a.分类 || ''); 项.appendChild(链接);
        列表.appendChild(项);
    });
    结果容器.appendChild(列表);
}

function 同一文章ID(文章, id) { return 文章 && id != null && String(文章.id) === String(id); }

function 打开文章详情(文章) {
    if (!文章 || 文章.id == null) return;
    状态.当前文章ID = String(文章.id); 状态.当前详情文章 = 文章; 状态.当前页面 = '详情';
    history.pushState(null, '', 构建详情Hash(文章)); 显示文章详情(文章.分类 || '');
}

function 打开文章详情ById(id, 分类 = '') {
    const 文章=[...状态.首页精选文章,...状态.文章列表,...状态.搜索扩展文章].find(a => 同一文章ID(a, id) && (!分类 || a.分类 === 分类));
    if (文章) 打开文章详情(文章); else { 状态.当前文章ID = String(id); 显示文章详情(分类); }
}

function 激活详情视图() {
    document.querySelectorAll('.页面视图').forEach(v=>v.classList.remove('活跃视图'));
    document.querySelectorAll('.导航链接').forEach(l=>l.classList.remove('活跃'));
    const dv=document.getElementById('详情视图'); if(dv)dv.classList.add('活跃视图');
    return document.getElementById('详情容器');
}

async function 查找详情文章(id, 分类 = '') {
    const 已加载 = [状态.当前详情文章, ...状态.首页精选文章, ...状态.文章列表, ...状态.搜索扩展文章,
        ...Object.values(状态.专题缓存).flatMap(数据 => Array.isArray(数据.articles) ? 数据.articles : []),
        ...(状态.金融缓存 && Array.isArray(状态.金融缓存.articles) ? 状态.金融缓存.articles : [])];
    let 文章 = 已加载.find(a => 同一文章ID(a, id) && (!分类 || a.分类 === 分类 || (分类 === '金融' && !a.分类)));
    if (文章) return 文章;

    const 待读取 = [];
    if (专题栏目文件[分类]) 待读取.push(获取专题数据(分类));
    else if (分类 === '金融') 待读取.push(获取金融数据());
    else if (!分类) {
        Object.keys(专题栏目文件).forEach(栏目 => 待读取.push(获取专题数据(栏目)));
        待读取.push(获取金融数据());
    }
    const 结果 = await Promise.allSettled(待读取);
    return 结果.filter(项 => 项.status === 'fulfilled')
        .flatMap(项 => Array.isArray(项.value.articles) ? 项.value.articles : [])
        .find(a => 同一文章ID(a, id)) || null;
}

async function 显示文章详情(分类 = '') {
    const c = 激活详情视图(); if (!c) return;
    if (!状态.当前文章ID) {
        c.innerHTML = '<div class="详情错误"><h1>文章地址无效</h1><p>这个链接缺少文章编号，请返回首页重新选择。</p><button class="详情返回" onclick="切换页面(\'首页\')">← 返回首页</button></div>';
        return;
    }
    c.innerHTML = '<p class="搜索提示">正在加载文章…</p>';
    const 请求ID = String(状态.当前文章ID);
    let 文章 = null;
    try { 文章 = await 查找详情文章(请求ID, 分类); }
    catch (错误) { console.warn('详情加载失败：' + 错误.message); }
    if (String(状态.当前文章ID) !== 请求ID) return;
    if (!文章) {
        c.innerHTML = '';
        const 错误区 = document.createElement('div'); 错误区.className = '详情错误';
        添加文本元素(错误区, 'h1', '', '文章暂时无法打开');
        添加文本元素(错误区, 'p', '', `没有找到编号为 ${请求ID} 的文章。链接可能已过期，也可能是数据源暂时不可用。`);
        const 返回 = 添加文本元素(错误区, 'button', '详情返回', '← 返回首页'); 返回.onclick = () => 切换页面('首页');
        c.appendChild(错误区); return;
    }
    状态.当前详情文章 = 文章;
    // 清理标题尾部来源后缀，如" - zjw.cn"、" - 新浪网"
    const 原始标题 = 文章.标题 || '';
    const 清洗标题 = 原始标题.replace(/[—–-]\s*[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}(?:\/[^\s]*)?\s*$/, '').trim() || 原始标题;
    const 原标题 = 获取原标题(文章);
    const 原标题HTML = 原标题 && 原标题 !== 原始标题 ? `<p class="详情原标题" lang="en">${转义HTML(原标题)}</p>` : '';
    // 清理导语中重复标题前缀（如情感板块的固定句式）
    let 导语HTML = '';
    if (文章.导语) {
        let 清洗导语 = 文章.导语;
        const 导语前缀匹配 = 清洗导语.match(/^(这项研究为理解['"]?).+?['"]?提供了/);
        if (导语前缀匹配) 清洗导语 = '▎ ' + 清洗导语.slice(导语前缀匹配[0].length);
        导语HTML = `<p class="详情导语">${转义HTML(清洗导语)}</p>`;
    }
    // 过滤 AI 翻译指令类"要点"（如"关注研究讨论的问题"等通用模板，不是给用户看的）
    const 真实要点 = Array.isArray(文章.要点) ? 文章.要点.filter(点 => {
        const 模板要点 = ['关注研究讨论的问题','区分研究关联与因果结论','结合原论文理解适用范围','发生了什么','涉及哪些主体','后续值得关注什么'];
        return 模板要点.indexOf(点.trim()) === -1 && 点.trim().length > 10;
    }) : [];
    const 正文原文 = 文章.正文 || 文章.内容 || 文章.摘要 || '暂无详细内容。';
    // 分离正文中的免责声明模板（"这是基于论文…"类文字）
    let 清洗正文 = 正文原文;
    const 免责声明匹配 = 清洗正文.match(/[。，；][这是基于论文题目|这是基于公开|本短稿依据公开|只帮助理解研究线索，不替代原论文，也不构成诊断、治疗或个体化医疗建议|本短稿为资料性改写]+.*$/);
    if (免责声明匹配) 清洗正文 = 清洗正文.slice(0, 免责声明匹配.index + 1);
    const 段落 = 清洗正文.split('\n').filter(p=>p.trim()).map(p => {
        const 行 = p.trim(); const 标题匹配 = 行.match(/^(#{1,3})\s+(.+)/);
        if (标题匹配) { const 标签 = 标题匹配[1].length === 1 ? 'h2' : 'h3'; return `<${标签}>${转义HTML(标题匹配[2])}</${标签}>`; }
        return `<p>${转义HTML(行)}</p>`;
    }).join('');
    const 要点HTML = 真实要点.length
        ? `<section class="详情要点"><h2>阅读要点</h2><ul>${真实要点.map(点 => `<li>${转义HTML(点)}</li>`).join('')}</ul></section>` : '';
    // 只对真实配图展示封面框，占位封面（assets/covers/）不显示
    const 封面 = 获取文章图片(文章);
    const 封面HTML = 封面 && !/assets\/covers\//i.test(封面) ? `<figure class="详情封面"><img src="${转义HTML(封面)}" alt="${转义HTML(清洗标题)}" decoding="async" fetchpriority="high"></figure>` : '';
    const 原文 = 安全外链(文章.原文链接 || 文章.链接);
    const 出处 = 文章.出处说明 || 文章.版权 || (文章.来源 ? '内容整理自 ' + 文章.来源 + '，版权归原作者及原机构所有。' : '');
    const 出处HTML = 出处 || 原文 ? `<aside class="详情出处"><strong>出处说明</strong><p>${转义HTML(出处)}</p>${原文 ? `<a href="${转义HTML(原文)}" target="_blank" rel="noopener" class="详情来源链接">查看原始出处</a>` : ''}</aside>` : '';
    c.innerHTML=`<button class="详情返回" onclick="切换页面('首页')">&larr; 返回</button>${封面HTML}<h1 class="详情标题">${转义HTML(清洗标题)}</h1>${原标题HTML}<div class="详情元信息"><span>来源：${转义HTML(文章.来源||'')}</span><span>${转义HTML(文章.日期||'')}</span><span>分类：${转义HTML(文章.分类||分类||'')}</span>${文章.热度?'<span>热度 '+转义HTML(文章.热度)+'</span>':''}</div>${导语HTML}${要点HTML}<div class="详情正文">${清洗正文 ? 段落 : ''}</div>${出处HTML}`;
    window.scrollTo({top:0,behavior:'smooth'});
}

function 切换移动菜单() {
    const 菜单 = document.getElementById('导航菜单'); const 按钮 = document.querySelector('.菜单按钮');
    if (!菜单 || !按钮) return;
    const 已展开 = 菜单.classList.toggle('展开'); 按钮.classList.toggle('展开', 已展开);
    按钮.setAttribute('aria-expanded', String(已展开)); 按钮.setAttribute('aria-label', 已展开 ? '关闭菜单' : '打开菜单');
}
function 监听滚动() {
    const 返回按钮=document.getElementById('返回顶部');
    window.addEventListener('scroll',()=>{
        if(返回按钮) 返回按钮.classList.toggle('可见',window.scrollY>600);
    });
}
function 滚动到顶部(){window.scrollTo({top:0,behavior:'smooth'});}

// ============================================================
// 分类标签展开/收起
// ============================================================

function 初始化分类折叠() {
    const 组 = document.getElementById('分类标签组');
    if (!组) return;
    const 标签列表 = 组.querySelectorAll(':scope > .分类标签');
    const 折叠阈值 = 10; // 显示前10个标签（全部~金融），折叠后4个
    if (标签列表.length <= 折叠阈值) return;

    // 给后几个标签添加折叠类并隐藏
    for (let i = 折叠阈值; i < 标签列表.length; i++) {
        标签列表[i].classList.add('折叠标签', 'hidden');
    }

    // 创建展开/收起按钮
    const 按钮 = document.createElement('button');
    按钮.className = '展开按钮';
    按钮.textContent = '展开全部 ▸';
    按钮.setAttribute('aria-label', '展开更多分类');
    let 已展开 = false;
    按钮.onclick = (e) => {
        e.stopPropagation();
        已展开 = !已展开;
        for (let i = 折叠阈值; i < 标签列表.length; i++) {
            标签列表[i].classList.toggle('hidden', !已展开);
        }
        按钮.textContent = 已展开 ? '收起 ▾' : '展开全部 ▸';
        按钮.setAttribute('aria-label', 已展开 ? '收起多余分类' : '展开更多分类');
        if (已展开 && 标签列表.length > 0) {
            标签列表[标签列表.length - 1].scrollIntoView({ behavior: 'smooth', inline: 'end', block: 'nearest' });
        }
    };
    组.appendChild(按钮);
}
