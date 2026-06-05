/* ============================================================
   极光引擎 · 前端脚本
   布局：4等大卡片(2x2) → 一手消息(文字行) → 更多资讯(文字行) → GitHub工具
   最后修改：见 修改登记.json
   ============================================================ */

const 状态 = {
    当前页面: '首页', 当前分类: '全部', 排序方式: '最新',
    搜索关键词: '', 文章列表: [], 已筛选文章: [],
    来源集合: new Set(), 当前文章ID: null,
};

document.addEventListener('DOMContentLoaded', async () => {
    await 初始化数据();
    初始化路由();
    渲染当前页面();
    监听滚动();
});

// ============================================================
// 数据加载
// ============================================================

async function 初始化数据() {
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
    更新分类计数();
    更新更新时间();
}

function 更新统计() {
    const 总数 = 状态.文章列表.length;
    const 今日 = 状态.文章列表.filter(a => { try { return a.日期 && a.日期.includes(获取今日日期()); } catch { return false; } }).length;
    ['文章总数','今日新增','覆盖来源'].forEach((id, i) => {
        const el = document.getElementById(id);
        if (el) el.textContent = [总数, 今日, 状态.来源集合.size][i];
    });
}
function 获取今日日期() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function 更新分类计数() {
    ['大模型', 'AI应用', 'AI绘画', '学术前沿', '行业动态', '开源工具'].forEach(分类 => {
        const 计数 = 状态.文章列表.filter(a => a.分类 === 分类).length;
        const 元素 = document.getElementById(`计数-${分类}`);
        if (元素) 元素.textContent = `${计数} 篇`;
    });
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
    if (window.location.hash.slice(1) !== 页面名) history.replaceState(null, '', '#' + 页面名);
    switch (页面名) { case '首页': 渲染首页(); break; case '分类': 更新分类计数(); break; case '搜索': 初始化搜索(); break; }
    const 菜单 = document.getElementById('导航菜单'); const 按钮 = document.querySelector('.菜单按钮');
    if (菜单) 菜单.classList.remove('展开'); if (按钮) 按钮.classList.remove('展开');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================
// 首页渲染
// ============================================================

function 渲染首页() { 应用筛选(); }

function 应用筛选() {
    let 文章列表 = [...状态.文章列表];
    if (状态.当前分类 !== '全部') 文章列表 = 文章列表.filter(a => a.分类 === 状态.当前分类);
    if (状态.排序方式 === '最热') 文章列表.sort((a, b) => (b.热度 || 0) - (a.热度 || 0));

    // 工具排行 / 一手消息 作为独立分类
    if (状态.当前分类 === '工具排行') {
        clearContainers();
        加载工具排行();
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }
    if (状态.当前分类 === '一手消息') {
        clearContainers();
        const 一手来源 = ['The Information', 'Stratechery', 'Stanford HAI', 'Anthropic Blog',
            'CVPR 2026 现场报道', 'World Arena 独家访谈', 'ArXiv 论文解读', 'Steersman AI Blog', 'Variety'];
        const 一手列表 = 文章列表.filter(a => 一手来源.includes(a.来源));
        if (一手列表.length > 0) {
            渲染纯一手容器(一手列表);
        }
        if (空状态) 空状态.style.display = 一手列表.length === 0 ? 'block' : 'none';
        if (加载区域) 加载区域.style.display = 'none';
        return;
    }

    const 空状态 = document.getElementById('空状态');
    const 加载区域 = document.getElementById('加载区域');
    if (文章列表.length === 0) {
        if (空状态) 空状态.style.display = 'block';
        if (加载区域) 加载区域.style.display = 'none';
        clearContainers();
    } else {
        if (空状态) 空状态.style.display = 'none';
        if (加载区域) 加载区域.style.display = 'none';

        // 分离一手消息
        const 一手来源 = ['The Information', 'Stratechery', 'Stanford HAI', 'Anthropic Blog',
            'CVPR 2026 现场报道', 'World Arena 独家访谈', 'ArXiv 论文解读', 'Steersman AI Blog', 'Variety'];
        const 一手消息列表 = 文章列表.filter(a => 一手来源.includes(a.来源));
        const 常规文章列表 = 文章列表.filter(a => !一手来源.includes(a.来源));

        const 特征文章 = 常规文章列表.slice(0, 4);
        const 列表文章 = 常规文章列表.slice(4);

        渲染容器(状态.当前分类, 特征文章, 一手消息列表, 列表文章);
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

/** 统一渲染：根据当前分类展示对应容器 */
function 渲染容器(分类, 特征文章, 一手消息列表, 列表文章) {
    clearContainers();

    // 特征区 — 分类不为"全部"时标注分类名
    if (特征文章.length > 0) {
        const 容器 = document.getElementById('特征容器');
        if (容器) {
            const 标题 = document.createElement('div'); 标题.className = '特征区标题';
            标题.textContent = 分类 === '全部' ? '今日推荐' : 分类;
            容器.appendChild(标题);
            const 网格 = document.createElement('div'); 网格.className = '特征网格';
            // 桌面端精确列数，手机端交给CSS媒体查询
            if (window.innerWidth > 700) {
                if (特征文章.length === 4) 网格.style.gridTemplateColumns = '1fr 1fr';
                else if (特征文章.length === 3) 网格.style.gridTemplateColumns = 'repeat(3, 1fr)';
                else if (特征文章.length === 2) 网格.style.gridTemplateColumns = '1fr 1fr';
                else 网格.style.gridTemplateColumns = '1fr';
            }
            特征文章.forEach(a => 网格.appendChild(创建特征卡片(a)));
            容器.appendChild(网格);
        }
    }

    // 一手消息区 — 只在全部分类或原生资讯时显示
    if (一手消息列表.length > 0 && (分类 === '全部')) {
        const 容器 = document.getElementById('一手容器');
        if (容器) {
            const 标题 = document.createElement('div'); 标题.className = '一手标题'; 标题.textContent = '一手消息';
            容器.appendChild(标题);
            const 列表 = document.createElement('ul'); 列表.className = '一手列表';
            一手消息列表.forEach(文章 => {
                创建一手行(文章, 列表);
            });
            容器.appendChild(列表);
        }
    }

    // 更多资讯
    if (列表文章.length > 0) {
        const 容器 = document.getElementById('列表容器');
        if (容器) {
            const 标题 = document.createElement('div'); 标题.className = '列表区域标题'; 标题.textContent = '更多资讯';
            容器.appendChild(标题);
            const 列表 = document.createElement('ul'); 列表.className = '资讯列表';
            列表文章.forEach(文章 => {
                const 项 = document.createElement('li'); 项.className = '资讯列表项';
                const 链接 = document.createElement('a'); 链接.className = '资讯列表链接';
                链接.href='#详情/'+文章.id; 链接.onclick=(e)=>{e.preventDefault();打开文章详情(文章);};
                链接.innerHTML=`<div class="列表元信息"><span class="列表来源">${文章.来源||''}</span><span class="列表分隔">·</span><span class="列表日期">${文章.日期||''}</span></div><span class="列表标题">${文章.标题||''}</span><span class="列表分类">${文章.分类||''}</span>`;
                项.appendChild(链接); 列表.appendChild(项);
            });
            容器.appendChild(列表);
        }
    }

}

/** 一手消息作为独立容器时（全列表，无特征卡片） */
function 渲染纯一手容器(文章列表) {
    const 容器 = document.getElementById('特征容器');
    if (!容器 || 文章列表.length === 0) return;
    const 标题 = document.createElement('div'); 标题.className = '特征区标题'; 标题.textContent = '一手消息';
    容器.appendChild(标题);
    const 列表 = document.createElement('ul'); 列表.className = '一手列表';
    文章列表.forEach(a => 创建一手行(a, 列表));
    容器.appendChild(列表);
}

function 创建一手行(文章, 列表) {
    const 项 = document.createElement('li'); 项.className = '一手列表项';
    const 链接 = document.createElement('a'); 链接.className = '一手列表链接';
    链接.href='#详情/'+文章.id; 链接.onclick=(e)=>{e.preventDefault();打开文章详情(文章);};
    链接.innerHTML=`<span class="一手标记">一手</span><span class="一手来源">${文章.来源||''}</span><span class="一手日期">${文章.日期||''}</span><span class="一手标题文字">${文章.标题||''}</span>`;
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
// GitHub 工具排行
// ============================================================

async function 加载工具排行() {
    const 容器 = document.getElementById('工具容器');
    if (!容器) return;

    let 工具列表 = [];
    try {
        const 响应 = await fetch('GitHub工具排行.json?v=' + Date.now());
        if (响应.ok) 工具列表 = await 响应.json();
    } catch (e) { console.log('工具排行加载失败：' + e.message); }

    if (工具列表.length === 0) return;

    const 标题 = document.createElement('div'); 标题.className = '工具标题'; 标题.textContent = 'GitHub 工具排行';
    容器.appendChild(标题);
    const 列表 = document.createElement('ul'); 列表.className = '工具列表';

    工具列表.forEach(工具 => {
        const 项 = document.createElement('li'); 项.className = '工具列表项';
        项.innerHTML = `
            <span class="工具名">${工具.名称 || ''}<a class="工具链接" href="${工具.链接 || '#'}" target="_blank" rel="noopener">&nearr;</a></span>
            <span class="工具说明">${工具.说明 || ''}</span>
            <span class="工具排行标记">${工具.星标 || ''} stars</span>`;
        列表.appendChild(项);
    });
    容器.appendChild(列表);
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
    if (分类名 === '工具排行') {
        // 直接切到首页渲染工具区
        切换页面('首页');
    } else {
        切换页面('首页');
    }
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
    结果容器.innerHTML = `<p style="margin-bottom:24px;color:var(--text-faint);font-size:var(--text-sm)">找到 <span style="color:var(--brass);font-weight:600">${结果.length}</span> 篇</p>`;
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

function 打开文章详情(文章) { if (!文章||!文章.id) return; 状态.当前文章ID=文章.id; 状态.当前页面='详情'; history.pushState(null,'','#详情/'+文章.id); 显示文章详情(); }
function 打开文章详情ById(id) { const 文章=状态.文章列表.find(a=>a.id===id); if(文章) 打开文章详情(文章); }

function 显示文章详情() {
    const 文章 = 状态.文章列表.find(a=>a.id===状态.当前文章ID);
    if(!文章){切换页面('首页');return;}
    document.querySelectorAll('.页面视图').forEach(v=>v.classList.remove('活跃视图'));
    document.querySelectorAll('.导航链接').forEach(l=>l.classList.remove('活跃'));
    const dv=document.getElementById('详情视图'); if(dv)dv.classList.add('活跃视图');
    const c=document.getElementById('详情容器'); if(!c)return;
    const 段落 = (文章.内容||文章.摘要||'暂无').split('\n').filter(p=>p.trim()).map(p=>p.trim().match(/^#{1,3}\s/)?`<${p.match(/^(#{1,3})/)[1].length===1?'h2':'h3'}>${p.replace(/^#{1,3}\s/,'')}</${p.match(/^(#{1,3})/)[1].length===1?'h2':'h3'}>`:`<p>${p.trim()}</p>`).join('');
    c.innerHTML=`<button class="详情返回" onclick="切换页面('首页')">&larr; 返回</button><h1 class="详情标题">${文章.标题||''}</h1><div class="详情元信息"><span>来源：${文章.来源||''}</span><span>${文章.日期||''}</span><span>分类：${文章.分类||''}</span>${文章.热度?'<span>热度 '+文章.热度+'</span>':''}</div><div class="详情正文">${段落||'<p>暂无详细内容。</p>'}</div>${文章.链接?'<a href="'+文章.链接+'" target="_blank" class="详情来源链接">阅读原文 &rarr;</a>':''}`;
    window.scrollTo({top:0,behavior:'smooth'});
}

function 切换移动菜单() { document.getElementById('导航菜单').classList.toggle('展开'); document.querySelector('.菜单按钮').classList.toggle('展开'); }
function 监听滚动() {
    const 返回按钮=document.getElementById('返回顶部'), 导航栏=document.getElementById('导航栏');
    let 上次滚动=0;
    window.addEventListener('scroll',()=>{
        if(返回按钮) 返回按钮.classList.toggle('可见',window.scrollY>600);
        if(导航栏){if(window.scrollY>上次滚动&&window.scrollY>200)导航栏.classList.add('隐藏');else 导航栏.classList.remove('隐藏');}
        上次滚动=window.scrollY;
    });
}
function 滚动到顶部(){window.scrollTo({top:0,behavior:'smooth'});}

window.addEventListener('popstate',()=>{
    const hash=window.location.hash.slice(1);
    if(hash.startsWith('详情/')){const id=parseInt(hash.split('详情/')[1]);if(id){状态.当前文章ID=id;状态.当前页面='详情';显示文章详情();return;}}
    if(hash&&['首页','分类','搜索','关于'].includes(hash))切换页面(hash);else 切换页面('首页');
});
