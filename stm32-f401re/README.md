# SiloRobot STM32 firmware

NUCLEO-F401RE에서 모터 드라이버 2개(모터 4개)를 제어하는 베어메탈 펌웨어입니다.
STM32CubeIDE + HAL을 사용하며, Jetson Nano B01과 ST-LINK VCP(USART2, 115200bps)로 통신합니다.

> [!warning] 볼트에 남은 과거 코드 스냅샷
> 개발·빌드에 사용하지 않는다. 최신 코드는 `D:\SiloRobot\stm32-controller`, 옵시디언 핀맵은
> [[2. 하드웨어/05. 배선도]] 하나만 사용한다.

현재 저장소에는 순수 C 제어 코어와 HAL 진입점의 과거 사본이 있습니다.
ST 공식 STM32CubeF4 CMSIS/HAL 소스는 `ThirdParty/`에 포함돼
있으며, 별도의 Cube 패키지 다운로드 없이 ARM 빌드할 수 있습니다.

## 확정 프로토콜

- Nano → STM32: `[AA][CMD][throttle_i8][turn_i8][xor][55]`
- STM32 → Nano: `[BB][TLM][d1][d2][d3][flags][xor][55]`
- `CMD`: `01` 이동, `02` 정지 래치, `03` 정지 해제
- 주기: 20Hz, 통신 타임아웃: 300ms
- `flags`: bit0 정지 래치, bit1 통신 타임아웃 이력

## ARM 펌웨어 빌드

CubeIDE에서 `File > Import > Existing Projects into Workspace`로 이 폴더를 가져올 수 있습니다.
Google Drive 폴더는 링커의 임시 파일 교체를 간헐적으로 막으므로 빌드 출력은 로컬 임시 폴더를
권장합니다.

```powershell
$env:PATH="<CubeIDE ARM GCC bin>;<CubeIDE make bin>;$env:PATH"
make BUILD_DIR=C:/Users/<user>/AppData/Local/Temp/silorobot-f401-build
```

생성물: `silorobot-f401re.elf`, `.hex`, `.bin`. 2026-08-16 빌드 기준 Flash 11,444B, RAM 1,976B.

## PC 코어 단위시험

```powershell
gcc -std=c11 -Wall -Wextra -Werror -IApp/Inc App/Src/*.c tests/test_main.c -o tests/test_main.exe
./tests/test_main.exe
```

## 실물 연결 후 남은 작업

- 엔코더 핀은 실물 신호 확인 뒤 배정
- UART RX 바이트를 `silo_protocol_push_byte()`에 전달
- 1ms tick에서 `silo_controller_tick()` 호출
- `SiloMotorOutput`을 실제 PWM compare/direction GPIO에 반영
- ADC 원시값을 실측 보정된 mm 값으로 변환해 텔레메트리 전송

## 안전 동작

- 부팅 직후 정지 래치, 명시적 해제 전까지 PWM 0
- 유효 명령이 300ms 끊기면 즉시 정지 래치
- 비상정지는 감속 램프 없이 즉시 PWM 0
- 일반 속도/방향 변경은 10 permille/ms로 제한해 최대 출력에서 0까지 약 100ms 감속
- 정·역방향 전환은 반드시 0을 거친 다음 반대 방향으로 증가
