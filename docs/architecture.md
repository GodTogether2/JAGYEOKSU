# 아키텍처

도메인은 입력 정규화, 분석 오케스트레이션, 결과 전달, 외부 AI 어댑터로 나뉜다. `AnalysisConnector` 프로토콜이 Service와 Ollama 클라이언트를 분리해 기능별 병렬 개발과 테스트 대역 주입을 가능하게 한다. 모든 경계 데이터는 Pydantic v2로 검증한다.

결과 전달 Service는 AI Connector가 반환한 `AnomalyLLMResult`를 최초 요청 포맷에 `analysis_result` 키로 붙여 downstream endpoint로 전송한다. 전송 URL은 `RESULT_FORWARD_ENDPOINT_URL`로 설정하며, 값이 비어 있으면 로컬 개발과 테스트를 위해 전송을 생략한다.

보안 경계에서는 개인정보 필드를 `extra="forbid"`로 거부하고, 로그에는 마스킹 식별자와 처리 메타데이터만 남긴다. 전체 시계열은 프로세스 로그와 응답에 포함하지 않는다.
