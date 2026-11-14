"""User-configured image APIs. Keys never enter image metadata or task manifests."""
import base64,json,uuid,re,time
from pathlib import Path
from urllib.parse import urlsplit,quote,urljoin
import requests
from PyQt6.QtCore import QBuffer,QByteArray,QIODevice
from PyQt6.QtGui import QImage,QImageReader
import engine as E
from prompt_enhancer import protect,EnhancementError

KINDS=[('images','OpenAI Images Compatible'),('gemini','Google Gemini (generateContent)')]
MAX_BYTES=40*1024*1024
class ImageError(ValueError):pass

def defaults():return dict(kind='images',url='',api_key='',model='')
def validate(c):
    try:u=urlsplit(c.get('url','').strip());_=u.port
    except ValueError:raise ImageError('Invalid URL / 接口地址无效') from None
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment:raise ImageError('Enter an HTTP(S) base URL without keys or query parameters / 请填写不含密钥和查询参数的接口地址')
    if c.get('kind') not in dict(KINDS):raise ImageError('Choose an image API type / 请选择图像接口格式')
    if not c.get('model','').strip():raise ImageError('Enter an image-generation model name / 请填写支持图像生成的模型名')
    if c['kind']=='gemini' and not c.get('api_key'):raise ImageError('Enter API KEY / 请填写 API KEY')
def load_config(folder):
    cfg=defaults()
    try:
        saved=json.loads((Path(folder)/'image_settings.json').read_text('utf-8'));cfg.update({k:v for k,v in saved.items() if k in cfg and k!='api_key'})
        if saved.get('protected_key'):
            try:cfg['api_key']=protect(saved['protected_key'],True)
            except EnhancementError:cfg['key_locked']=True
    except (OSError,ValueError):pass
    return cfg

def save_config(folder,c):
    validate(c);data={k:c[k] for k in ('kind','url','model')};data['protected_key']=protect(c['api_key']) if c.get('api_key') else '';E.atomic_json(Path(folder)/'image_settings.json',data)

def endpoint(c,has_refs):
    base=c['url'].strip().rstrip('/');path=urlsplit(base).path
    if c['kind']=='gemini':
        if path.endswith(':generateContent'):return base
        return base+('/v1beta' if not path else '')+'/models/'+quote(c['model'].removeprefix('models/'),safe='')+':generateContent'
    for suffix in ('/images/generations','/images/edits'):
        if base.endswith(suffix):base=base[:-len(suffix)];break
    return base+('/v1' if not urlsplit(base).path else '')+('/images/edits' if has_refs else '/images/generations')

def reference_bytes(paths):
    if len(paths)>9:raise ImageError('At most 9 references / 最多 9 张参考图')
    result=[];total=0
    for path in paths:
        reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size()
        if not size.isValid() or size.width()*size.height()>25000000:raise ImageError('Reference cannot be read or exceeds 25 megapixels / 参考图片无法读取或超过 2500 万像素')
        image=reader.read()
        if image.isNull():raise ImageError('Cannot read reference image / 无法读取参考图片')
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer,'PNG'):raise ImageError('Cannot encode reference image / 无法编码参考图')
        raw=bytes(data);total+=len(raw)
        if total>15*1024*1024:raise ImageError('References exceed 15 MB after encoding; use smaller images / 参考图编码后总计超过 15 MB，请缩小图片')
        result.append(raw)
    return result

def request_data(c,prompt,refs):
    validate(c)
    if not prompt.strip() or len(prompt)>16000:raise ImageError('Enter a description (up to 16,000 characters) / 请填写描述，最多 16000 字符')
    url=endpoint(c,bool(refs));headers={};body=None;files=None
    if c['kind']=='images':
        if c.get('api_key'):headers['Authorization']='Bearer '+c['api_key']
        body=dict(model=c['model'].strip(),prompt=prompt,n=1)
        if refs:
            # Modelflare's GPT Image 2.5 gateway rejects multipart image[] in live tests.
            # Its documented JSON edit contract preserves every reference in order.
            json_edits=(urlsplit(c['url']).hostname=='modelflare.dev' and c['model'].strip() in ('gpt-image-2.5-sunburst','gpt-image-2.5-flare'))
            if json_edits:
                body['images']=[{'image_url':'data:image/png;base64,'+base64.b64encode(raw).decode('ascii')} for raw in refs]
                if any(len(item['image_url'])>20971520 for item in body['images']):raise ImageError('Reference exceeds the provider data URL limit; use a smaller image / 参考图超过服务商内嵌图片上限，请缩小图片')
            else:
                field='image' if len(refs)==1 else 'image[]'
                files=[(field,(f'reference_{i+1}.png',raw,'image/png')) for i,raw in enumerate(refs)]
    else:
        headers['x-goog-api-key']=c['api_key'];parts=[{'text':prompt}]
        parts.extend({'inlineData':{'mimeType':'image/png','data':base64.b64encode(raw).decode('ascii')}} for raw in refs)
        body={'contents':[{'role':'user','parts':parts}],'generationConfig':{'responseModalities':['TEXT','IMAGE']}}
    return url,headers,body,files

def bounded_response(response,limit):
    chunks=[];size=0
    try:
        for chunk in response.iter_content(65536):
            size+=len(chunk)
            if size>limit:raise ImageError('API response is too large / 接口返回过大')
            chunks.append(chunk)
        return b''.join(chunks)
    finally:response.close()

def decode64(value):
    try:
        if len(value)>MAX_BYTES*4//3+16:raise ValueError()
        return base64.b64decode(value,validate=True)
    except (ValueError,TypeError):raise ImageError('Invalid returned image data / 返回图片数据无效') from None

def download(url):
    # Never send provider authorization/cookies to a returned image URL.
    with requests.Session() as client:
        client.trust_env=False
        for _ in range(4):
            u=urlsplit(url)
            if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:raise ImageError('Invalid image download URL / 图片下载地址无效')
            r=client.get(url,timeout=(15,90),stream=True,allow_redirects=False)
            if r.status_code in (301,302,303,307,308):
                location=r.headers.get('Location','');r.close()
                if not location:break
                url=urljoin(url,location);continue
            if r.status_code!=200:r.close();raise ImageError('Image download failed / 图片下载失败')
            return bounded_response(r,MAX_BYTES)
    raise ImageError('Too many image redirects / 图片地址重定向过多')

def parse_images(kind,data):
    images=[]
    if kind=='images':
        for item in data.get('data',[])[:4]:
            if item.get('b64_json'):images.append(decode64(item['b64_json']))
            elif item.get('url'):images.append(download(item['url']))
    else:
        for candidate in data.get('candidates',[])[:4]:
            for part in candidate.get('content',{}).get('parts',[]):
                inline=part.get('inlineData',part.get('inline_data',{}))
                if not part.get('thought') and inline.get('data'):images.append(decode64(inline['data']))
                if len(images)>=4:break
    if not images:raise ImageError('No image returned. Check that the selected model supports image output and the API format matches / 未返回图片，请检查模型是否支持图像生成及接口格式是否匹配')
    return images[:4]

def save_images(folder,images):
    decoded=[]
    for raw in images:
        data=QByteArray(raw);buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buffer);size=reader.size()
        if not size.isValid() or size.width()*size.height()>40000000:raise ImageError('Returned image is invalid or too large / 返回图片无效或尺寸过大')
        image=reader.read()
        if image.isNull():raise ImageError('Cannot decode generated image / 无法解码生成的图片')
        decoded.append(image)
    folder=Path(folder)/'generated_images';folder.mkdir(parents=True,exist_ok=True);paths=[]
    for image in decoded:
        path=folder/(uuid.uuid4().hex+'.png')
        if not image.save(str(path),'PNG'):raise ImageError('Cannot save image to workspace / 无法将图片保存到工作目录')
        paths.append(str(path))
    return paths


def safe_error_text(value,c,prompt=''):
    text=str(value)
    # Providers sometimes echo request fields. Never expose those in diagnostics.
    for secret in (c.get('api_key',''),prompt,c.get('url','')):
        if secret:text=text.replace(secret,'[redacted]')
    text=re.sub(r'(?i)(bearer\s+)[^\s,;"\}]+',r'\1[redacted]',text)
    text=re.sub(r'(?i)sk-[a-z0-9_-]{8,}','[redacted]',text)
    text=re.sub(r'(?i)((?:api[_-]?key|authorization|token)\s*[=:]\s*)[^\s,;]+',r'\1[redacted]',text)
    return ' '.join(text.split())[:900]

def api_error(response,c,prompt):
    status=response.status_code;data={}
    try:data=json.loads(bounded_response(response,65536))
    except (ValueError,ImageError):pass
    if not isinstance(data,dict):data={}
    error=data.get('error',{})
    if not isinstance(error,(dict,str)):error={}
    code=safe_error_text(error.get('code') or error.get('type') or '' if isinstance(error,dict) else '',c,prompt)
    message=safe_error_text(error.get('message','') if isinstance(error,dict) else error,c,prompt)
    if not message:message=safe_error_text(data.get('message',''),c,prompt)
    identifier=safe_error_text(data.get('request_id') or (error.get('request_id') if isinstance(error,dict) else '') or '',c,prompt)
    low=(code+' '+message).lower()
    if any(x in low for x in ['content_policy','safety','moderation','content_filter']):
        hint='服务商内容审核未通过，请查看具体原因 / Provider content review rejected the request'
    elif 'unsupported_endpoint' in low:
        hint='模型与接口格式不匹配，请按服务商要求选择图像接口 / Model and API format do not match'
    elif any(x in low for x in ['insufficient_user_quota','insufficient_quota','budget_exhausted']):
        hint='服务商返回额度或预算不足 / Provider reports insufficient quota or budget'
    elif 'group' in low and any(x in low for x in ['model','route']):
        hint='当前密钥分组无法调用该模型，请检查服务商分组 / API key group cannot route this model'
    else:
        hint={400:'服务商拒绝了本次请求，请查看具体原因 / Provider rejected the request; see details',401:'密钥认证失败 / API key authentication failed',403:'服务商拒绝访问，请检查权限或预算 / Access denied; check permissions or budget',404:'接口地址或模型不存在 / Endpoint or model not found',429:'请求过于频繁或达到服务商限额 / Rate or provider limit reached'}.get(status,'图像服务暂时不可用，请查看服务商错误详情 / Image service unavailable; see provider details')
    lines=[f'HTTP {status}: {hint}']
    if code:lines.append('Code: '+code)
    if message:lines.append('服务商详情 / Provider: '+message)
    if identifier:lines.append('Request ID: '+identifier)
    if not message:lines.append('服务商未返回可读错误详情 / No readable error detail returned')
    return ImageError('\n'.join(lines))


def generate(c,prompt,paths,folder,session=None):
    refs=reference_bytes(paths);url,headers,body,files=request_data(c,prompt,refs);client=session or requests.Session();client.trust_env=False
    try:
        kwargs={'data':body,'files':files} if files else {'json':body}
        r=client.post(url,headers=headers,timeout=(20,240),allow_redirects=False,stream=True,**kwargs)
        if r.status_code!=200:
            raise api_error(r,c,prompt)
        data=json.loads(bounded_response(r,80*1024*1024));images=parse_images(c['kind'],data);result=save_images(folder,images)
        E.atomic_json(Path(folder)/'generated_images'/(Path(result[0]).stem+'.json'),dict(prompt=prompt,reference_count=len(paths),images=[Path(p).name for p in result]))
        return result
    except requests.RequestException:raise ImageError('Image request/download failed or timed out; no automatic retry. The provider may still have processed it / 请求或图片下载失败、超时，不会自动重试；服务商可能已处理请求') from None
    except (KeyError,TypeError,json.JSONDecodeError):raise ImageError('Unexpected image response format / 图像返回格式不匹配') from None
    finally:
        if session is None:client.close()
