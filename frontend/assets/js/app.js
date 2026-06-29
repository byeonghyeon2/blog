/**
 * app.js - Naver Blog Writer 프론트엔드 메인 스크립트
 *
 * 담당 기능:
 *  - AI 글 생성 (제목 / 본문 / SEO) 호출 및 로딩 표시
 *  - 글 저장 (POST), 업데이트 (PUT), 삭제 (DELETE)
 *  - 글 목록 조회 (작성 메모 검색 + 상태 필터)
 *  - 대시보드 요약 카운트 갱신
 *  - 클립보드 복사 (텍스트 / HTML)
 *  - 삭제 확인 모달
 */

'use strict';

// ───────────────────────────────────────────
// 상수 / 전역 상태
// ───────────────────────────────────────────

/**
 * FastAPI 백엔드 기준 URL.
 * 정적 파일과 API가 같은 서버에서 제공되므로 상대 경로('')로 충분합니다.
 */
const API = '';
const MAX_REFERENCE_IMAGE_COUNT = 12;

/**
 * 현재 편집 패널에 로드된 글 ID.
 * null이면 새 글, 숫자이면 기존 글 업데이트 모드입니다.
 * @type {number|null}
 */
let currentPostId = null;

/**
 * 사용자가 업로드한 본문 사진의 data URL 목록입니다.
 * OpenAI 호출 시 사진 분석과 본문 배치 참고용으로 함께 전달합니다.
 * @type {string[]}
 */
let referenceImageDataUrls = [];

/**
 * 업로드한 사진의 시간/파일명 메모입니다.
 * AI가 사진을 시간순으로 배치하도록 백엔드 프롬프트에 함께 전달합니다.
 * @type {string[]}
 */
let referenceImageNotes = [];

/**
 * 현재 표시할 화면을 전환합니다.
 * posts: 글 목록 화면, create: 글 작성/수정 화면
 *
 * @param {'posts'|'create'} viewName - 표시할 화면 이름
 */
function showView(viewName) {
    const normalized = ['posts', 'create', 'instagram'].includes(viewName) ? viewName : 'posts';

    $('#postsView').toggle(normalized === 'posts');
    $('#createView').toggle(normalized === 'create');
    $('#instagramView').toggle(normalized === 'instagram');

    $('[data-view-link]').removeClass('active');
    $(`[data-view-link="${normalized}"]`).addClass('active');

    if (window.location.hash !== `#${normalized}`) {
        window.location.hash = normalized;
    }

    syncCreatePanelHeights();
}

// ───────────────────────────────────────────
// 유틸리티 함수
// ───────────────────────────────────────────

/**
 * 화면 우하단에 짧은 안내 메시지를 표시합니다.
 * 2.2초 후 자동으로 사라집니다.
 *
 * @param {string}  message  - 표시할 메시지
 * @param {boolean} [isError=false] - true이면 에러 색상 적용
 */
function toast(message, isError = false) {
    const $el = $('#toast');
    $el
        .text(message)
        .toggleClass('toast--error', isError)
        .fadeIn(130);
    setTimeout(() => $el.fadeOut(180), 2200);
}

/**
 * AI 호출 중 화면 전체를 덮는 로딩 오버레이를 표시/해제합니다.
 * 오버레이가 활성화된 동안은 버튼 클릭이 차단됩니다.
 *
 * @param {boolean} isLoading   - true이면 오버레이 표시
 * @param {string}  [message]   - 오버레이에 표시할 안내 메시지
 */
function setLoading(isLoading, message = 'AI가 글을 생성하고 있습니다…') {
    $('#loadingOverlay').toggleClass('active', isLoading).attr('aria-hidden', !isLoading);
    $('#loadingMessage').text(message);

    // 생성하기 버튼에도 인라인 스피너를 함께 표시합니다.
    $('#btnGenerate')
        .prop('disabled', isLoading)
        .toggleClass('btn--loading', isLoading);
}

/**
 * 제목 textarea에서 첫 번째 유효한 제목 텍스트를 추출합니다.
 * AI가 "1. 제목A\n2. 제목B" 형태로 여러 후보를 반환한 경우
 * 번호와 점을 제거한 첫 번째 줄만 저장용 제목으로 사용합니다.
 *
 * @returns {string} 정리된 제목 문자열 (없으면 빈 문자열)
 */
function getFirstTitle() {
    const raw = $('#title').val().trim();
    const firstLine = raw.split('\n').find(Boolean) || raw;
    return firstLine.replace(/^\d+\.\s*/, '').trim();
}

/**
 * AI가 반환한 제목 후보 목록에서 첫 번째 제목을 자동 선택하여
 * 제목 textarea에 반영합니다.
 *
 * @param {string} result - AI 응답 원본 텍스트
 * @returns {string}        선택된 첫 번째 제목
 */
function setGeneratedTitle(result) {
    const firstTitle =
        result.split('\n').find(Boolean)?.replace(/^\d+\.\s*/, '').trim()
        || result.trim();
    $('#title').val(firstTitle);
    return firstTitle;
}

/**
 * 생성 API 공통 요청 본문(사용자 작성 메모 + 카테고리)을 반환합니다.
 * 호출 전 keyword가 비어있는지 확인하세요.
 *
 * @returns {{ keyword: string, category: string }}
 */
function requestBody() {
    return {
        keyword:   $('#keyword').val().trim(),
        category: $('#postType').val(),
        reference_image_data_urls: referenceImageDataUrls,
        reference_image_notes: referenceImageNotes,
    };
}

function syncIncludeCodeVisibility() {
    const isItCategory = $('#postType').val() === 'IT';
    $('#includeCodeGroup').toggle(isItCategory);
    if (!isItCategory) {
        $('#includeCode').prop('checked', false);
    }
}

/**
 * 긴 작성 메모를 목록에서 읽기 쉬운 길이로 줄입니다.
 *
 * @param {string|null|undefined} value - 원본 작성 메모
 * @param {number} [maxLength=64] - 표시할 최대 글자 수
 * @returns {string} 축약된 텍스트
 */
function compactMemo(value, maxLength = 64) {
    const normalized = String(value || '').replace(/\s+/g, ' ').trim();
    if (normalized.length <= maxLength) return normalized;
    return `${normalized.slice(0, maxLength)}...`;
}

function photoMarkerToHtml(line) {
    const match = line.match(/^\[(?:사진|이미지)\s*(\d+)\s*삽입(?::\s*(.*?))?\]$/);
    if (!match) return '';

    const photoNumber = Number(match[1]);
    const caption = (match[2] || `사진 ${photoNumber}`).trim();
    const imageUrl = referenceImageDataUrls[photoNumber - 1];

    if (!imageUrl) {
        return `
            <figure class="preview-photo-slot preview-photo-slot--empty">
                <div class="preview-photo-placeholder">사진 ${photoNumber}</div>
                <figcaption>${escapeHtml(caption)}</figcaption>
            </figure>
        `;
    }

    return `
        <figure class="preview-photo-slot">
            <img src="${imageUrl}" alt="${escapeHtml(caption)}">
            <figcaption>${escapeHtml(caption)}</figcaption>
        </figure>
    `;
}

/**
 * textarea 내용을 HTML 미리보기로 변환합니다.
 * 실제 저장 HTML과 완전히 같지는 않지만, 작성 중 읽힘새를 확인하기 위한 가벼운 렌더러입니다.
 *
 * @param {string} value - 원본 텍스트
 * @returns {string} 미리보기용 HTML
 */
function previewTextToHtml(value) {
    const escaped = escapeHtml(value || '');
    return escaped
        .split(/\n{2,}/)
        .map((block) => {
            const line = block.trim();
            if (!line) return '';
            const photoHtml = photoMarkerToHtml(line);
            if (photoHtml) return photoHtml;
            if (/^\d+\.\s/.test(line)) {
                return `<h3>${line}</h3>`;
            }
            return `<p>${line.replaceAll('\n', '<br>')}</p>`;
        })
        .join('');
}

/**
 * SEO 결과에서 태그처럼 보이는 값을 추출해 글 하단에 가볍게 표시합니다.
 * SEO 설명 전체를 카드로 보여주지 않고, 실제 블로그의 태그 영역처럼 보이게 하기 위함입니다.
 *
 * @param {string} value - SEO 원본 텍스트
 * @returns {string} 미리보기용 태그 HTML
 */
function previewSeoToHtml(value) {
    const tags = String(value || '')
        .split(/[\n,#]/)
        .map((tag) => tag.replace(/^(태그|tags?|키워드)\s*[:：-]?\s*/i, '').trim())
        .filter(Boolean)
        .slice(0, 8);

    if (!tags.length) return '';

    return `
        <div class="preview-tags">
            ${tags.map((tag) => `<span>#${escapeHtml(tag.replace(/^#/, ''))}</span>`).join('')}
        </div>
    `;
}

/**
 * 현재 작성 영역의 제목/본문/SEO 값을 조합해 최종 글 미리보기를 갱신합니다.
 */
function buildNaverClipboardHtml(title, contentText, seoText) {
    return `
        <article>
            ${title ? `<h1>${escapeHtml(title)}</h1>` : ''}
            ${contentText ? previewTextToHtml(contentText) : ''}
            ${seoText ? previewSeoToHtml(seoText) : ''}
        </article>
    `.trim();
}

function updatePostPreview() {
    const title = getFirstTitle();
    const content = $('#contentText').val().trim();
    const seo = $('#seo').val().trim();

    if (!title && !content && !seo) {
        $('#postPreview').html('<p class="preview-empty">제목과 본문을 생성하면 이곳에 최종 글 형태로 표시됩니다.</p>');
        return;
    }

    $('#postPreview').html(`
        ${title ? `<h1>${escapeHtml(title)}</h1>` : ''}
        ${content ? `<div class="preview-content">${previewTextToHtml(content)}</div>` : ''}
        ${seo ? previewSeoToHtml(seo) : ''}
    `);

    syncCreatePanelHeights();
}

/**
 * 글 작성 화면의 좌측 "글 생성" 패널 높이를 우측 "생성 결과" 패널 높이에 맞춥니다.
 * 좁은 화면에서 두 패널이 세로로 쌓여도 시각적인 길이가 어긋나지 않도록 보정합니다.
 */
function syncCreatePanelHeights() {
    window.requestAnimationFrame(() => {
        const $inputPanel = $('.panel--input');
        const $editorPanel = $('.panel--editor');

        if (!$inputPanel.length || !$editorPanel.length || !$('#createView').is(':visible')) {
            return;
        }

        $inputPanel.css('min-height', `${Math.ceil($editorPanel.outerHeight())}px`);
    });
}

/**
 * jQuery $.ajax를 async/await에서 사용하기 위한 POST 래퍼입니다.
 *
 * @param {string} url     - 요청 URL
 * @param {object} payload - JSON으로 직렬화할 요청 본문
 * @returns {Promise<any>}
 */
async function postJson(url, payload) {
    return $.ajax({
        url,
        method:      'POST',
        contentType: 'application/json',
        data:        JSON.stringify(payload),
    });
}

/**
 * XSS 방어를 위해 테이블 등에 출력할 값의 HTML 특수문자를 이스케이프합니다.
 *
 * @param {string|null|undefined} value - 원본 값
 * @returns {string} 이스케이프된 안전한 문자열
 */
function escapeHtml(value) {
    return String(value || '')
        .replaceAll('&',  '&amp;')
        .replaceAll('<',  '&lt;')
        .replaceAll('>',  '&gt;')
        .replaceAll('"',  '&quot;')
        .replaceAll("'",  '&#039;');
}

/**
 * 글 상태 값을 한글 표시명으로 변환합니다.
 * 알 수 없는 상태는 원본 값을 그대로 반환합니다.
 *
 * @param {string} status - 상태 코드 (DRAFT, REVIEWING, ...)
 * @returns {string} 한글 표시명
 */
function statusLabel(status) {
    const map = {
        DRAFT:     '초안',
        REVIEWING: '검수중',
        READY:     '준비완료',
        PUBLISHED: '발행완료',
        ARCHIVED:  '보관',
    };
    return map[status] || status;
}

/**
 * 글 유형 코드를 한글 표시명으로 변환합니다.
 *
 * @param {string} type - 내부 카테고리 코드
 * @returns {string} 한글 표시명
 */
function typeLabel(type) {
    const map = {
        IT:        'IT / 기술',
        FINANCE:   '금융 / 재테크',
        FOOD:      '맛집 / 음식',
        TRAVEL:    '여행 / 장소',
        LIFESTYLE: '생활 / 리뷰',
    };
    return map[type] || type;
}

// ───────────────────────────────────────────
// 데이터 로드 함수
// ───────────────────────────────────────────

/**
 * 대시보드 요약 정보(전체/초안/검수중/발행완료 건수)를 API에서 불러와 갱신합니다.
 * 실패 시 카운트를 변경하지 않고 콘솔에 오류를 기록합니다.
 */
async function loadDashboard() {
    try {
        const data = await $.getJSON(`${API}/api/dashboard/summary`);
        $('#totalCount').text(data.total);
        $('#draftCount').text(data.status_counts.DRAFT      || 0);
        $('#reviewCount').text(data.status_counts.REVIEWING || 0);
        $('#publishedCount').text(data.status_counts.PUBLISHED || 0);
    } catch (err) {
        console.error('[loadDashboard] 대시보드 로드 실패:', err);
    }
}

/**
 * 글 목록을 API에서 불러와 테이블에 렌더링합니다.
 * 검색어와 상태 필터를 쿼리 파라미터로 전달합니다.
 * 결과가 없으면 빈 상태 메시지를 표시합니다.
 *
 * @param {string} [keyword='']  - 검색어 (title, topic_keyword 대상)
 * @param {string} [status='']   - 상태 필터 코드 (빈 문자열이면 전체)
 */
async function loadPosts(keyword = '', status = '') {
    try {
        // 쿼리 파라미터 조립 (빈 값은 제외)
        const params = {};
        if (keyword) params.keyword = keyword;
        if (status)  params.status  = status;

        const posts = await $.getJSON(`${API}/api/posts`, params);

        if (posts.length === 0) {
            // 결과 없음: 빈 상태 메시지 표시
            $('#postRows').empty();
            $('#emptyState').show();
            return;
        }

        $('#emptyState').hide();

        // 테이블 행 렌더링 (XSS 방어를 위해 escapeHtml 적용)
        const rows = posts.map((post) => `
            <tr data-id="${post.id}">
                <td>
                    <span style="font-family:var(--font-mono);color:var(--color-text-muted);font-size:11px;">
                        #${post.id}
                    </span>
                </td>
                <td>
                    <button class="link-btn" data-open="${post.id}">
                        ${escapeHtml(post.title)}
                    </button>
                </td>
                <td style="color:var(--color-text-muted);" title="${escapeHtml(post.topic_keyword)}">${escapeHtml(compactMemo(post.topic_keyword))}</td>
                <td><span class="type-badge">${typeLabel(post.category)}</span></td>
                <td><span class="status-badge status-badge--${post.status}">${statusLabel(post.status)}</span></td>
                <td style="color:var(--color-text-muted);font-size:12px;white-space:nowrap;">
                    ${new Date(post.created_at).toLocaleString('ko-KR', { dateStyle: 'short', timeStyle: 'short' })}
                </td>
            </tr>
        `);
        $('#postRows').html(rows.join(''));
    } catch (err) {
        console.error('[loadPosts] 글 목록 로드 실패:', err);
        toast('목록을 불러오는 중 오류가 발생했습니다.', true);
    }
}

// ───────────────────────────────────────────
// 편집 패널 갱신 함수
// ───────────────────────────────────────────

/**
 * 편집 패널 상태를 지정된 글 ID에 맞게 업데이트합니다.
 * ID가 null이면 "새 글" 모드로 초기화합니다.
 *
 * @param {number|null} postId - 편집 중인 글 ID (null이면 새 글)
 */
function updateCurrentPostUI(postId) {
    currentPostId = postId;

    if (postId !== null) {
        // 기존 글 편집 모드: 배지와 삭제 버튼 표시
        $('#currentPostIdLabel').text(postId);
        $('#currentPostBadge').show();
        $('#btnDelete').show();
    } else {
        // 새 글 모드: 배지와 삭제 버튼 숨김
        $('#currentPostBadge').hide();
        $('#btnDelete').hide();
    }
}

/**
 * 목록에서 클릭한 글의 전체 데이터를 API에서 불러와 편집 패널에 채웁니다.
 * 로드에 실패하면 에러 토스트를 표시합니다.
 *
 * @param {number} postId - 불러올 글의 ID
 */
async function openPost(postId) {
    if (!postId || isNaN(postId)) {
        return toast('유효하지 않은 글 ID입니다.', true);
    }

    try {
        const post = await $.getJSON(`${API}/api/posts/${postId}`);

        // 편집 패널 각 필드에 데이터 채우기
        $('#keyword').val(post.topic_keyword);
        $('#postType').val(post.category);
        $('#title').val(post.title);
        $('#contentText').val(post.content_text || '');

        // SEO 설명(첫 줄)과 태그(나머지)를 하나의 textarea에 표시
        $('#seo').val([post.seo_description, post.tags_text].filter(Boolean).join('\n'));

        // 글 상태 드롭다운 설정 (없으면 DRAFT 기본값)
        const status = post.status || 'DRAFT';
        $('#postStatus').val(status).attr('data-status', status);

        syncIncludeCodeVisibility();
        updateCurrentPostUI(post.id);
        updatePostPreview();

        // 작성 화면으로 전환합니다.
        showView('create');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        toast('글을 불러왔습니다.');
    } catch (err) {
        console.error('[openPost] 글 로드 실패:', err);
        toast('글을 불러오는 중 오류가 발생했습니다.', true);
    }
}

// ───────────────────────────────────────────
// AI 생성 함수
// ───────────────────────────────────────────

/**
 * 사용자가 적은 작성 메모와 카테고리를 기반으로 블로그 제목 후보 5개를 AI로 생성합니다.
 * 생성 후 첫 번째 제목을 자동으로 textarea에 반영합니다.
 *
 * @returns {Promise<string|undefined>} 선택된 첫 번째 제목 (유효성 실패 시 undefined)
 */
async function generateTitle() {
    const body = requestBody();
    if (!body.keyword) {
        toast('작성 메모를 입력해주세요.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/title`, body);
    setGeneratedTitle(data.result);
    updatePostPreview();
    toast('제목을 생성했습니다.');
    return getFirstTitle();
}

/**
 * 제목과 작성 메모를 기준으로 실제 블로그 본문을 AI로 생성합니다.
 * 작성 메모와 제목이 모두 필요합니다.
 *
 * @returns {Promise<string|undefined>} 생성된 본문 텍스트 (유효성 실패 시 undefined)
 */
async function generateContent() {
    const base  = requestBody();
    const title = getFirstTitle();

    if (!base.keyword || !title) {
        toast('작성 메모와 제목이 필요합니다.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/content`, {
        ...base,
        title,
        include_code:  $('#includeCode').is(':checked'),
        target_length: Number($('#targetLength').val()) || 2500,
    });
    $('#contentText').val(data.result);
    updatePostPreview();
    toast('본문을 생성했습니다.');
    return data.result;
}

/**
 * 생성된 본문을 기준으로 SEO 설명과 네이버 블로그 태그를 AI로 생성합니다.
 * 작성 메모, 제목, 본문이 모두 필요합니다.
 *
 * @returns {Promise<string|undefined>} 생성된 SEO 텍스트 (유효성 실패 시 undefined)
 */
async function generateSeo() {
    const base        = requestBody();
    const title       = getFirstTitle();
    const contentText = $('#contentText').val().trim();

    if (!base.keyword || !title || !contentText) {
        toast('작성 메모, 제목, 본문이 모두 필요합니다.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/seo`, {
        title,
        keyword:      base.keyword,
        content_text: contentText,
    });
    $('#seo').val(data.result);
    updatePostPreview();
    toast('SEO 정보를 생성했습니다.');
    return data.result;
}

/**
 * 생성 항목 드롭다운 선택값에 따라 필요한 AI API를 순서대로 호출합니다.
 * ALL이면 제목 → 본문 → SEO 순서로 전체 생성합니다.
 * 각 단계 실패 시 나머지 단계를 중단하지 않고 에러 토스트만 표시합니다.
 */
async function generateSelected() {
    const mode = $('#generationMode').val();

    setLoading(true, modeToLoadingMessage(mode));
    try {
        if (mode === 'TITLE') {
            await generateTitle();
            return;
        }
        if (mode === 'CONTENT') {
            await generateContent();
            return;
        }
        if (mode === 'SEO') {
            await generateSeo();
            return;
        }

        // ALL: 전체 순서대로 실행
        setLoading(true, '제목 생성 중…');
        await generateTitle();

        setLoading(true, '본문 생성 중…');
        await generateContent();

        setLoading(true, 'SEO 생성 중…');
        await generateSeo();

        toast('전체 글 생성을 완료했습니다.');
    } catch (err) {
        // API 에러 응답에서 detail 메시지를 우선 사용
        const message = err?.responseJSON?.detail || '생성 중 오류가 발생했습니다.';
        toast(message, true);
        console.error('[generateSelected] 생성 오류:', err);
    } finally {
        setLoading(false);
    }
}

/**
 * 생성 모드 코드를 로딩 오버레이 메시지로 변환합니다.
 *
 * @param {string} mode - 생성 모드 코드
 * @returns {string} 한글 로딩 메시지
 */
function modeToLoadingMessage(mode) {
    const map = {
        TITLE:   '제목 생성 중…',
        CONTENT: '본문 생성 중…',
        SEO:     'SEO 생성 중…',
        ALL:     'AI가 전체 글을 생성하고 있습니다…',
    };
    return map[mode] || 'AI가 글을 생성하고 있습니다…';
}

// ───────────────────────────────────────────
// 글 저장 / 삭제 함수
// ───────────────────────────────────────────

/**
 * 편집 패널 내용을 DB에 저장합니다.
 * currentPostId가 있으면 PUT(업데이트), 없으면 POST(새 글 생성)를 호출합니다.
 * 저장 성공 시 대시보드와 목록을 자동으로 갱신합니다.
 */
/**
 * 카드뉴스 생성 요청에 사용할 입력값을 모읍니다.
 * URL만 넣거나, 직접 작성한 글만 넣거나, 둘 다 넣는 방식 모두 지원합니다.
 *
 * @returns {object} 인스타 카드뉴스 생성 API 요청 본문
 */
function instagramRequestBody() {
    const category = $('#instaCategory').val();
    return {
        source_type: $('#instaSourceType').val(),
        source_url: $('#instaSourceUrl').val().trim(),
        source_text: $('#instaSourceText').val().trim(),
        card_count: Number($('#instaCardCount').val()) || 6,
        category: category || null,
        purpose: $('#instaPurpose').val(),
        style_note: $('#instaStyleNote').val().trim(),
    };
}

/**
 * AI가 반환한 카드뉴스 원고를 카드 단위 객체로 파싱합니다.
 * 출력 형식이 조금 흔들려도 제목/본문/이미지 설명을 최대한 분리해서 미리보기에 사용합니다.
 *
 * @param {string} text - AI가 생성한 카드뉴스 원고
 * @returns {{number:number,title:string,body:string,image:string}[]} 카드 목록
 */
function parseInstagramCards(text) {
    const blocks = String(text || '')
        .split(/(?=\[카드\s*\d+\])/g)
        .map((block) => block.trim())
        .filter((block) => block.startsWith('[카드'));

    return blocks.map((block, index) => {
        const numberMatch = block.match(/\[카드\s*(\d+)\]/);
        const titleMatch = block.match(/제목\s*:\s*(.+)/);
        const imageMatch = block.match(/이미지\s*:\s*(.+)/);
        const bodyMatch = block.match(/본문\s*:\s*([\s\S]*?)(?=\n이미지\s*:|\n\[카드|\n해시태그\s*:|$)/);

        return {
            number: Number(numberMatch?.[1]) || index + 1,
            title: (titleMatch?.[1] || '').trim(),
            body: (bodyMatch?.[1] || '').trim(),
            image: (imageMatch?.[1] || '').trim(),
        };
    });
}

/**
 * 카드뉴스 원고를 인스타 카드 형태의 미리보기로 렌더링합니다.
 * 실제 디자인 이미지는 아니고, 카드별 카피와 이미지 방향을 검수하기 위한 초안 화면입니다.
 *
 * @param {string} text - 카드뉴스 원고
 */
function renderInstagramPreview(text) {
    const cards = parseInstagramCards(text);

    if (!cards.length) {
        $('#instaCardPreview').html('<p class="preview-empty">자료를 입력하고 카드뉴스를 만들면 카드별 미리보기가 표시됩니다.</p>');
        return;
    }

    $('#instaCardPreview').html(cards.map((card) => `
        <article class="insta-card">
            <div class="insta-card__top">
                <span class="insta-card__number">${card.number}</span>
                <h3>${escapeHtml(card.title || `카드 ${card.number}`)}</h3>
                <p>${escapeHtml(card.body).replaceAll('\n', '<br>')}</p>
            </div>
            ${card.image ? `<div class="insta-card__image-note">${escapeHtml(card.image)}</div>` : ''}
        </article>
    `).join(''));
}

/**
 * URL/블로그 글/정보성 글을 인스타 카드뉴스 원고로 생성합니다.
 * 버튼을 누르는 시점에만 OpenAI API를 호출하므로, 호출할 때마다 토큰 비용이 발생합니다.
 */
async function generateInstagramCards() {
    const payload = instagramRequestBody();

    if (!payload.source_url && !payload.source_text) {
        return toast('URL 또는 카드뉴스로 만들 내용을 입력해 주세요.', true);
    }

    setLoading(true, '카드뉴스 원고를 생성하고 있습니다...');
    try {
        const data = await postJson(`${API}/api/ai/instagram-cards`, payload);
        $('#instaResultText').val(data.result);
        renderInstagramPreview(data.result);
        toast('카드뉴스 원고가 생성되었습니다.');
    } catch (err) {
        const message = err?.responseJSON?.detail || '카드뉴스 생성 중 오류가 발생했습니다.';
        toast(message, true);
        console.error('[generateInstagramCards] 생성 오류:', err);
    } finally {
        setLoading(false);
    }
}

/**
 * 카드뉴스 원고 textarea 내용을 클립보드로 복사합니다.
 */
async function copyInstagramText() {
    const text = $('#instaResultText').val();
    if (!text.trim()) {
        return toast('복사할 카드뉴스 원고가 없습니다.', true);
    }
    if (!navigator.clipboard) {
        return toast('클립보드 API를 지원하지 않는 환경입니다.', true);
    }

    try {
        await navigator.clipboard.writeText(text);
        toast('카드뉴스 원고를 복사했습니다.');
    } catch (err) {
        toast('카드뉴스 원고 복사에 실패했습니다.', true);
        console.error('[copyInstagramText] 복사 실패:', err);
    }
}

async function savePost() {
    const title   = getFirstTitle();
    const keyword = $('#keyword').val().trim();

    // 최소 필수 필드 검증
    if (!title)   return toast('제목이 비어있습니다. 먼저 제목을 생성하거나 입력하세요.', true);
    if (!keyword) return toast('작성 메모가 비어있습니다.', true);

    const seoText = $('#seo').val();
    const payload = {
        title,
        topic_keyword:   keyword,
        category:        $('#postType').val(),
        status:          $('#postStatus').val(),
        content_text:    $('#contentText').val(),
        seo_description: seoText.split('\n')[0] || '',
        tags_text:       seoText.split('\n').slice(1).join('\n'),
    };

    try {
        if (currentPostId) {
            // 기존 글 업데이트
            await $.ajax({
                url:         `${API}/api/posts/${currentPostId}`,
                method:      'PUT',
                contentType: 'application/json',
                data:        JSON.stringify(payload),
            });
            toast('글을 업데이트했습니다.');
        } else {
            // 새 글 생성
            const post = await postJson(`${API}/api/posts`, payload);
            updateCurrentPostUI(post.id);
            toast('글을 저장했습니다.');
        }

        await loadDashboard();
        await loadPosts(
            $('#searchKeyword').val().trim(),
            $('#filterStatus').val(),
        );
        showView('posts');
    } catch (err) {
        const message = err?.responseJSON?.detail || '저장 중 오류가 발생했습니다.';
        toast(message, true);
        console.error('[savePost] 저장 오류:', err);
    }
}

/**
 * 현재 편집 중인 글을 서버에서 삭제합니다.
 * currentPostId가 없으면 삭제 모달을 열지 않습니다.
 * 삭제 성공 시 편집 패널을 초기화하고 목록을 갱신합니다.
 */
async function deleteCurrentPost() {
    if (!currentPostId) {
        return toast('저장된 글만 삭제할 수 있습니다.', true);
    }

    try {
        await $.ajax({
            url:    `${API}/api/posts/${currentPostId}`,
            method: 'DELETE',
        });

        // 편집 패널 초기화 (새 글 모드)
        resetEditor();
        await loadDashboard();
        await loadPosts();
        showView('posts');
        toast('글을 삭제했습니다.');
    } catch (err) {
        const message = err?.responseJSON?.detail || '삭제 중 오류가 발생했습니다.';
        toast(message, true);
        console.error('[deleteCurrentPost] 삭제 오류:', err);
    }
}

/**
 * 편집 패널의 모든 입력 필드를 초기값으로 리셋합니다.
 * 새 글 작성 시작 또는 삭제 후 호출합니다.
 */
function resetEditor() {
    $('#keyword').val('');
    $('#postType').val('IT');
    syncIncludeCodeVisibility();
    $('#title').val('');
    $('#contentText').val('');
    $('#seo').val('');
    clearReferenceImage();
    $('#postStatus').val('DRAFT').attr('data-status', 'DRAFT');
    updateCurrentPostUI(null);
    updatePostPreview();
}

/**
 * 참고 이미지 선택 값을 초기화합니다.
 */
function clearReferenceImage() {
    referenceImageDataUrls = [];
    referenceImageNotes = [];
    $('#referenceImage').val('');
    $('#referenceImageList').empty();
    $('#referenceImagePreview').hide();
}

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function readFileAsArrayBuffer(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
    });
}

function readExifAscii(view, offset, count) {
    let value = '';
    for (let i = 0; i < count; i += 1) {
        const code = view.getUint8(offset + i);
        if (code === 0) break;
        value += String.fromCharCode(code);
    }
    return value.trim();
}

function parseExifDateTime(value) {
    const match = String(value || '').match(/^(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/);
    if (!match) return null;
    const [, year, month, day, hour, minute, second] = match.map(Number);
    return new Date(year, month - 1, day, hour, minute, second);
}

function findExifDateInIfd(view, tiffStart, ifdOffset, littleEndian, depth = 0) {
    if (!ifdOffset || depth > 2) return null;

    const entryCount = view.getUint16(tiffStart + ifdOffset, littleEndian);
    for (let i = 0; i < entryCount; i += 1) {
        const entryOffset = tiffStart + ifdOffset + 2 + (i * 12);
        const tag = view.getUint16(entryOffset, littleEndian);
        const type = view.getUint16(entryOffset + 2, littleEndian);
        const count = view.getUint32(entryOffset + 4, littleEndian);
        const valueOffset = view.getUint32(entryOffset + 8, littleEndian);

        if ((tag === 0x9003 || tag === 0x0132) && type === 2 && count > 0) {
            const date = parseExifDateTime(readExifAscii(view, tiffStart + valueOffset, count));
            if (date) return date;
        }

        if (tag === 0x8769) {
            const nestedDate = findExifDateInIfd(view, tiffStart, valueOffset, littleEndian, depth + 1);
            if (nestedDate) return nestedDate;
        }
    }

    return null;
}

async function extractPhotoTakenAt(file) {
    if (file.type !== 'image/jpeg') return null;

    try {
        const buffer = await readFileAsArrayBuffer(file);
        const view = new DataView(buffer);
        if (view.getUint16(0) !== 0xffd8) return null;

        let offset = 2;
        while (offset < view.byteLength) {
            if (view.getUint8(offset) !== 0xff) break;
            const marker = view.getUint8(offset + 1);
            const size = view.getUint16(offset + 2);
            if (marker === 0xe1 && readExifAscii(view, offset + 4, 6) === 'Exif') {
                const tiffStart = offset + 10;
                const littleEndian = readExifAscii(view, tiffStart, 2) === 'II';
                const firstIfdOffset = view.getUint32(tiffStart + 4, littleEndian);
                return findExifDateInIfd(view, tiffStart, firstIfdOffset, littleEndian);
            }
            offset += 2 + size;
        }
    } catch (err) {
        console.warn('[referenceImage] EXIF 읽기 실패:', err);
    }

    return null;
}

function formatPhotoTime(date) {
    if (!date) return '';
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function handleReferenceImageFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) {
        clearReferenceImage();
        return;
    }
    if (files.some((file) => !file.type.startsWith('image/'))) {
        toast('이미지 파일만 업로드할 수 있습니다.', true);
        clearReferenceImage();
        return;
    }
    if (files.length > MAX_REFERENCE_IMAGE_COUNT) {
        toast(`사진은 최대 ${MAX_REFERENCE_IMAGE_COUNT}장까지 선택해주세요.`, true);
        clearReferenceImage();
        return;
    }

    Promise.all(files.map(async (file, originalIndex) => {
        const [dataUrl, takenAt] = await Promise.all([
            readFileAsDataUrl(file),
            extractPhotoTakenAt(file),
        ]);
        const fileTime = file.lastModified ? new Date(file.lastModified) : null;
        const sortTime = takenAt || fileTime;
        return {
            name: file.name,
            dataUrl,
            takenAt,
            fileTime,
            sortValue: sortTime ? sortTime.getTime() : Number.MAX_SAFE_INTEGER,
            originalIndex,
        };
    }))
        .then((items) => {
            items.sort((a, b) => (a.sortValue - b.sortValue) || (a.originalIndex - b.originalIndex));
            referenceImageDataUrls = items.map((item) => item.dataUrl);
            referenceImageNotes = items.map((item, index) => {
                const takenTime = formatPhotoTime(item.takenAt);
                const fileTime = formatPhotoTime(item.fileTime);
                const timeText = takenTime
                    ? `촬영 시간 ${takenTime}`
                    : fileTime
                        ? `파일 수정 시간 ${fileTime}`
                        : '시간 정보 없음';
                return `사진 ${index + 1}: ${item.name}, ${timeText}`;
            });
            $('#referenceImageList').html(items.map((item, index) => `
                <div class="image-reference-item">
                    <img src="${item.dataUrl}" alt="본문 사진 ${index + 1}">
                    <span>사진 ${index + 1}</span>
                    <small>${escapeHtml(formatPhotoTime(item.takenAt) || formatPhotoTime(item.fileTime) || '시간 정보 없음')}</small>
                </div>
            `).join(''));
            $('#referenceImagePreview').show();
            updatePostPreview();
            toast(`사진 ${items.length}장을 불러왔습니다.`);
        })
        .catch((err) => {
            toast('이미지를 읽는 중 오류가 발생했습니다.', true);
            clearReferenceImage();
            console.error('[referenceImage] 이미지 읽기 실패:', err);
        });
}

// ───────────────────────────────────────────
// 클립보드 복사 함수
// ───────────────────────────────────────────

/**
 * 본문 텍스트를 클립보드에 복사합니다.
 * 본문이 비어있으면 복사하지 않습니다.
 * navigator.clipboard가 없는 구형 브라우저 환경에서는 에러 토스트를 표시합니다.
 */
async function copyText() {
    const text = $('#contentText').val();

    if (!text.trim()) {
        return toast('복사할 본문이 없습니다.', true);
    }

    // navigator.clipboard는 HTTPS 또는 localhost에서만 동작합니다.
    if (!navigator.clipboard) {
        return toast('클립보드 API를 지원하지 않는 환경입니다.', true);
    }

    try {
        await navigator.clipboard.writeText(text);
        toast('본문 텍스트를 복사했습니다.');
    } catch (err) {
        toast('클립보드 복사에 실패했습니다.', true);
        console.error('[copyText] 복사 실패:', err);
    }
}

/**
 * 본문 텍스트를 네이버 블로그에 붙여넣기 쉬운 HTML로 서버에서 변환한 뒤 클립보드에 복사합니다.
 * 제목 또는 본문이 비어있으면 변환을 요청하지 않습니다.
 */
async function copyHtml() {
    const title       = getFirstTitle();
    const keyword     = $('#keyword').val().trim();
    const contentText = $('#contentText').val().trim();
    const seoText     = $('#seo').val().trim();

    if (!contentText) {
        return toast('변환할 본문이 없습니다.', true);
    }
    if (!title) {
        return toast('제목이 필요합니다. 제목을 먼저 입력해주세요.', true);
    }

    // navigator.clipboard 지원 여부 확인
    if (!navigator.clipboard) {
        return toast('클립보드 API를 지원하지 않는 환경입니다.', true);
    }

    try {
        const html = buildNaverClipboardHtml(title, contentText, seoText);
        if (window.ClipboardItem && navigator.clipboard.write) {
            await navigator.clipboard.write([
                new ClipboardItem({
                    'text/html':  new Blob([html], { type: 'text/html' }),
                    'text/plain': new Blob([contentText], { type: 'text/plain' }),
                }),
            ]);
        } else {
            const data = await postJson(`${API}/api/ai/html-convert`, {
                title,
                keyword,
                content_text: contentText,
            });
            await navigator.clipboard.writeText(data.result);
        }
        toast('네이버 블로그에 붙여넣을 HTML을 복사했습니다.');
    } catch (err) {
        const message = err?.responseJSON?.detail || 'HTML 변환 중 오류가 발생했습니다.';
        toast(message, true);
        console.error('[copyHtml] HTML 변환 실패:', err);
    }
}

// ───────────────────────────────────────────
// 이벤트 바인딩
// ───────────────────────────────────────────

// 글 목록 행 클릭 → 이벤트 위임으로 동적 행에도 동작
$(document).on('click', '[data-open]', function () {
    openPost(Number($(this).data('open')));
});

// 생성하기 버튼
$('#btnGenerate').on('click', generateSelected);

// 인스타 카드뉴스 생성/복사 버튼
$('#btnGenerateInsta').on('click', generateInstagramCards);
$('#btnCopyInsta').on('click', copyInstagramText);
$('#instaResultText').on('input', function () {
    renderInstagramPreview($(this).val());
});

// 글 저장 버튼
$('#btnSave').on('click', savePost);

// 본문 텍스트 복사 버튼
$('#btnCopyText').on('click', copyText);

// HTML 복사 버튼
$('#btnCopyHtml').on('click', copyHtml);

// 새 글 버튼: 편집 패널 초기화
$('#btnNewPost').on('click', () => {
    resetEditor();
    toast('새 글 작성을 시작합니다.');
});

// 목록 화면에서 새 글 작성 버튼 클릭
$('#btnGoCreate').on('click', () => {
    resetEditor();
    showView('create');
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// 상단 네비게이션으로 화면 전환
$('[data-view-link]').on('click', function (event) {
    event.preventDefault();
    const target = $(this).data('view-link');
    if (target === 'create') {
        resetEditor();
    }
    showView(target);
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// 삭제 버튼: 확인 모달 열기
$('#btnDelete').on('click', () => {
    if (!currentPostId) return;
    $('#deleteModal').addClass('active').attr('aria-hidden', 'false');
});

// 삭제 모달 - 삭제 확인
$('#btnDeleteConfirm').on('click', async () => {
    $('#deleteModal').removeClass('active').attr('aria-hidden', 'true');
    await deleteCurrentPost();
});

// 삭제 모달 - 취소
$('#btnDeleteCancel').on('click', () => {
    $('#deleteModal').removeClass('active').attr('aria-hidden', 'true');
});

// 모달 배경 클릭 시 닫기
$('#deleteModal').on('click', function (e) {
    if ($(e.target).is('#deleteModal')) {
        $(this).removeClass('active').attr('aria-hidden', 'true');
    }
});

// 새로고침 버튼
$('#btnReload').on('click', async () => {
    await loadDashboard();
    await loadPosts(
        $('#searchKeyword').val().trim(),
        $('#filterStatus').val(),
    );
    toast('목록을 새로고침했습니다.');
});

// 검색어 입력: 300ms 디바운스 처리 (타이핑마다 API 호출 방지)
let searchDebounceTimer = null;
$('#searchKeyword').on('input', function () {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        loadPosts($(this).val().trim(), $('#filterStatus').val());
    }, 300);
});

// 상태 필터 변경 시 즉시 목록 갱신
$('#filterStatus').on('change', function () {
    loadPosts($('#searchKeyword').val().trim(), $(this).val());
});

// 글 상태 드롭다운 변경 시 색상 클래스 갱신
$('#postType').on('change', syncIncludeCodeVisibility);

$('#postStatus').on('change', function () {
    $(this).attr('data-status', $(this).val());
});

// 본문 사진 업로드: 브라우저에서 data URL로 읽어 OpenAI 요청에 함께 전달합니다.
$('#referenceImage').on('change', function () {
    handleReferenceImageFiles(this.files);
});

$('#referenceImageDropzone')
    .on('click keydown', function (event) {
        if (event.type === 'click' || event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            $('#referenceImage').trigger('click');
        }
    })
    .on('dragenter dragover', function (event) {
        event.preventDefault();
        event.stopPropagation();
        $(this).addClass('is-dragover');
    })
    .on('dragleave dragend drop', function (event) {
        event.preventDefault();
        event.stopPropagation();
        $(this).removeClass('is-dragover');
        if (event.type === 'drop') {
            handleReferenceImageFiles(event.originalEvent.dataTransfer.files);
        }
    });

$('#btnClearReferenceImage').on('click', clearReferenceImage);

// 작성 중에도 미리보기가 계속 갱신되도록 처리합니다.
$('#title, #contentText, #seo').on('input', () => {
    updatePostPreview();
    syncCreatePanelHeights();
});

$(window).on('resize', syncCreatePanelHeights);

// ───────────────────────────────────────────
// 초기 로드
// ───────────────────────────────────────────

/**
 * 페이지 로드 시 대시보드와 글 목록을 불러옵니다.
 * jQuery $(function) 은 DOM ready 이후 실행을 보장합니다.
 */
$(async function () {
    await loadDashboard();
    await loadPosts();
    syncIncludeCodeVisibility();
    updatePostPreview();
    const initialView = window.location.hash === '#create'
        ? 'create'
        : (window.location.hash === '#instagram' ? 'instagram' : 'posts');
    showView(initialView);
    syncCreatePanelHeights();
});
