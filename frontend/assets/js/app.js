/**
 * app.js - Tistory IT Blog Writer 프론트엔드 메인 스크립트
 *
 * 담당 기능:
 *  - AI 글 생성 (제목 / 목차 / 본문 / SEO) 호출 및 로딩 표시
 *  - 글 저장 (POST), 업데이트 (PUT), 삭제 (DELETE)
 *  - 글 목록 조회 (키워드 검색 + 상태 필터)
 *  - 대시보드 요약 카운트 갱신
 *  - 클립보드 복사 (텍스트 / HTML)
 *  - 검수 체크리스트 진행률 표시
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

/**
 * 현재 편집 패널에 로드된 글 ID.
 * null이면 새 글, 숫자이면 기존 글 업데이트 모드입니다.
 * @type {number|null}
 */
let currentPostId = null;

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
 * 생성 API 공통 요청 본문(키워드 + 글 유형)을 반환합니다.
 * 호출 전 keyword가 비어있는지 확인하세요.
 *
 * @returns {{ keyword: string, post_type: string }}
 */
function requestBody() {
    return {
        keyword:   $('#keyword').val().trim(),
        post_type: $('#postType').val(),
    };
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
 * @param {string} type - 유형 코드 (CONCEPT, TOOL_GUIDE, ...)
 * @returns {string} 한글 표시명
 */
function typeLabel(type) {
    const map = {
        CONCEPT:      '개념설명',
        TOOL_GUIDE:   '툴가이드',
        ERROR_FIX:    '에러해결',
        COMPARE:      '비교분석',
        CODE_EXAMPLE: '예제코드',
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
 * 검색 키워드와 상태 필터를 쿼리 파라미터로 전달합니다.
 * 결과가 없으면 빈 상태 메시지를 표시합니다.
 *
 * @param {string} [keyword='']  - 키워드 검색어 (title, topic_keyword 대상)
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
                <td style="color:var(--color-text-muted);">${escapeHtml(post.topic_keyword)}</td>
                <td><span class="type-badge">${typeLabel(post.post_type)}</span></td>
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
        $('#postType').val(post.post_type);
        $('#title').val(post.title);
        $('#outline').val(post.outline   || '');
        $('#contentText').val(post.content_text || '');

        // SEO 설명(첫 줄)과 태그(나머지)를 하나의 textarea에 표시
        $('#seo').val([post.seo_description, post.tags_text].filter(Boolean).join('\n'));

        // 글 상태 드롭다운 설정 (없으면 DRAFT 기본값)
        const status = post.status || 'DRAFT';
        $('#postStatus').val(status).attr('data-status', status);

        updateCurrentPostUI(post.id);

        // 편집 패널 상단으로 부드럽게 스크롤
        $('html').animate({ scrollTop: $('#create').offset().top - 80 }, 300);
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
 * 키워드와 글 유형을 기반으로 블로그 제목 후보 5개를 AI로 생성합니다.
 * 생성 후 첫 번째 제목을 자동으로 textarea에 반영합니다.
 *
 * @returns {Promise<string|undefined>} 선택된 첫 번째 제목 (유효성 실패 시 undefined)
 */
async function generateTitle() {
    const body = requestBody();
    if (!body.keyword) {
        toast('키워드를 입력해주세요.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/title`, body);
    setGeneratedTitle(data.result);
    toast('제목을 생성했습니다.');
    return getFirstTitle();
}

/**
 * 선택된 제목을 기준으로 번호형 목차를 AI로 생성합니다.
 * 제목 textarea가 비어있으면 중단합니다.
 *
 * @returns {Promise<string|undefined>} 생성된 목차 텍스트 (유효성 실패 시 undefined)
 */
async function generateOutline() {
    const base  = requestBody();
    const title = getFirstTitle();

    if (!base.keyword || !title) {
        toast('키워드와 제목이 필요합니다.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/outline`, { ...base, title });
    $('#outline').val(data.result);
    $('#title').val(title);
    toast('목차를 생성했습니다.');
    return data.result;
}

/**
 * 목차를 기준으로 실제 블로그 본문을 AI로 생성합니다.
 * 키워드, 제목, 목차 세 가지가 모두 필요합니다.
 *
 * @returns {Promise<string|undefined>} 생성된 본문 텍스트 (유효성 실패 시 undefined)
 */
async function generateContent() {
    const base    = requestBody();
    const title   = getFirstTitle();
    const outline = $('#outline').val().trim();

    if (!base.keyword || !title || !outline) {
        toast('키워드, 제목, 목차가 모두 필요합니다.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/content`, {
        ...base,
        title,
        outline,
        include_code:  $('#includeCode').is(':checked'),
        target_length: Number($('#targetLength').val()) || 2500,
    });
    $('#contentText').val(data.result);
    toast('본문을 생성했습니다.');
    return data.result;
}

/**
 * 생성된 본문을 기준으로 SEO 설명과 Tistory 태그를 AI로 생성합니다.
 * 키워드, 제목, 본문이 모두 필요합니다.
 *
 * @returns {Promise<string|undefined>} 생성된 SEO 텍스트 (유효성 실패 시 undefined)
 */
async function generateSeo() {
    const base        = requestBody();
    const title       = getFirstTitle();
    const contentText = $('#contentText').val().trim();

    if (!base.keyword || !title || !contentText) {
        toast('키워드, 제목, 본문이 모두 필요합니다.', true);
        return;
    }

    const data = await postJson(`${API}/api/ai/seo`, {
        title,
        keyword:      base.keyword,
        content_text: contentText,
    });
    $('#seo').val(data.result);
    toast('SEO 정보를 생성했습니다.');
    return data.result;
}

/**
 * 생성 항목 드롭다운 선택값에 따라 필요한 AI API를 순서대로 호출합니다.
 * ALL이면 제목 → 목차 → 본문 → SEO 순서로 전체 생성합니다.
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
        if (mode === 'OUTLINE') {
            await generateOutline();
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

        setLoading(true, '목차 생성 중…');
        await generateOutline();

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
        OUTLINE: '목차 생성 중…',
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
async function savePost() {
    const title   = getFirstTitle();
    const keyword = $('#keyword').val().trim();

    // 최소 필수 필드 검증
    if (!title)   return toast('제목이 비어있습니다. 먼저 제목을 생성하거나 입력하세요.', true);
    if (!keyword) return toast('키워드가 비어있습니다.', true);

    const seoText = $('#seo').val();
    const payload = {
        title,
        topic_keyword:   keyword,
        post_type:       $('#postType').val(),
        status:          $('#postStatus').val(),
        outline:         $('#outline').val(),
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
    $('#postType').val('CONCEPT');
    $('#title').val('');
    $('#outline').val('');
    $('#contentText').val('');
    $('#seo').val('');
    $('#postStatus').val('DRAFT').attr('data-status', 'DRAFT');
    updateCurrentPostUI(null);
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
 * 본문 텍스트를 Tistory용 HTML로 서버에서 변환한 뒤 클립보드에 복사합니다.
 * 제목 또는 본문이 비어있으면 변환을 요청하지 않습니다.
 */
async function copyHtml() {
    const title       = getFirstTitle();
    const keyword     = $('#keyword').val().trim();
    const contentText = $('#contentText').val().trim();

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
        const data = await postJson(`${API}/api/ai/html-convert`, {
            title,
            keyword,
            content_text: contentText,
        });
        await navigator.clipboard.writeText(data.result);
        toast('HTML을 복사했습니다.');
    } catch (err) {
        const message = err?.responseJSON?.detail || 'HTML 변환 중 오류가 발생했습니다.';
        toast(message, true);
        console.error('[copyHtml] HTML 변환 실패:', err);
    }
}

// ───────────────────────────────────────────
// 검수 체크리스트 진행률 관리
// ───────────────────────────────────────────

/**
 * 체크리스트의 체크된 항목 수를 세어 진행률 바와 레이블을 갱신합니다.
 * 체크리스트 내 체크박스가 변경될 때마다 자동으로 호출됩니다.
 */
function updateChecklistProgress() {
    const $items   = $('.checklist input[type="checkbox"]');
    const total    = $items.length;
    const checked  = $items.filter(':checked').length;
    const pct      = total > 0 ? Math.round((checked / total) * 100) : 0;

    $('#progressFill').css('width', `${pct}%`);
    $('#progressLabel').text(`${checked} / ${total}`);
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

// 키워드 검색: 300ms 디바운스 처리 (타이핑마다 API 호출 방지)
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
$('#postStatus').on('change', function () {
    $(this).attr('data-status', $(this).val());
});

// 체크리스트 변경 시 진행률 갱신
$(document).on('change', '.checklist input[type="checkbox"]', updateChecklistProgress);

// 체크리스트 전체 초기화
$('#btnClearChecklist').on('click', () => {
    $('.checklist input[type="checkbox"]').prop('checked', false);
    updateChecklistProgress();
    toast('체크리스트를 초기화했습니다.');
});

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
    updateChecklistProgress();
});
